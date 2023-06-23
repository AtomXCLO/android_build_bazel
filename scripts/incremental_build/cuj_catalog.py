# Copyright (C) 2022 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import functools
import io
import logging
import shutil
import tempfile
import textwrap
import uuid
from pathlib import Path
from typing import Final
from typing import Optional

import clone
import ui
import util
from cuj import CujGroup
from cuj import CujStep
from cuj import InWorkspace
from cuj import Verifier
from cuj import de_src
from cuj import skip_when_soong_only
from cuj import src

"""
Provides some representative CUJs. If you wanted to manually run something but
would like the metrics to be collated in the metrics.csv file, use
`perf_metrics.py` as a stand-alone after your build.
"""

Warmup: Final[CujGroup] = CujGroup('WARMUP',
                                   [CujStep('no change', lambda: None)])


def modify_revert(file: Path, text: Optional[str] = None) -> CujGroup:
  """
  :param file: the file to be modified and reverted
  :param text: the text to be appended to the file to modify it
  :return: A pair of CujSteps, where the first modifies the file and the
  second reverts the modification
  """
  if text is None:
    text = f'//BOGUS {uuid.uuid4()}\n'
  if not file.exists():
    raise RuntimeError(f'{file} does not exist')

  def add_line():
    with open(file, mode="a") as f:
      f.write(text)

  def revert():
    with open(file, mode="rb+") as f:
      # assume UTF-8
      f.seek(-len(text), io.SEEK_END)
      f.truncate()

  return CujGroup(de_src(file), [
      CujStep('modify', add_line),
      CujStep('revert', revert)
  ])


def create_delete(file: Path, ws: InWorkspace,
    text: Optional[str] = None) -> CujGroup:
  """
  :param file: the file to be created and deleted
  :param ws: the expectation for the counterpart file in symlink
  forest (aka the synthetic bazel workspace) when its created
  :param text: the content of the file
  :return: A pair of CujSteps, where the fist creates the file and the
  second deletes it
  """
  if text is None:
    text = f'//Test File: safe to delete {uuid.uuid4()}\n'
  missing_dirs = [f for f in file.parents if not f.exists()]
  shallowest_missing_dir = missing_dirs[-1] if len(missing_dirs) else None

  def create():
    if file.exists():
      raise RuntimeError(
          f'File {file} already exists. Interrupted an earlier run?\n'
          'TIP: `repo status` and revert changes!!!')
    file.parent.mkdir(parents=True, exist_ok=True)
    file.touch(exist_ok=False)
    with open(file, mode="w") as f:
      f.write(text)

  def delete():
    if shallowest_missing_dir:
      shutil.rmtree(shallowest_missing_dir)
    else:
      file.unlink(missing_ok=False)

  return CujGroup(de_src(file), [
      CujStep('create', create, ws.verifier(file)),
      CujStep('delete', delete, InWorkspace.OMISSION.verifier(file)),
  ])


def create_delete_bp(bp_file: Path) -> CujGroup:
  """
  This is basically the same as "create_delete" but with canned content for
  an Android.bp file.
  """
  return create_delete(
      bp_file, InWorkspace.SYMLINK,
      'filegroup { name: "test-bogus-filegroup", srcs: ["**/*.md"] }')


def delete_restore(original: Path, ws: InWorkspace) -> CujGroup:
  """
  :param original: The file to be deleted then restored
  :param ws: When restored, expectation for the file's counterpart in the
  symlink forest (aka synthetic bazel workspace)
  :return: A pair of CujSteps, where the first deletes a file and the second
  restores it
  """
  tempdir = Path(tempfile.gettempdir())
  if tempdir.is_relative_to(util.get_top_dir()):
    raise SystemExit(f'Temp dir {tempdir} is under source tree')
  if tempdir.is_relative_to(util.get_out_dir()):
    raise SystemExit(f'Temp dir {tempdir} is under '
                     f'OUT dir {util.get_out_dir()}')
  copied = tempdir.joinpath(f'{original.name}-{uuid.uuid4()}.bak')

  def move_to_tempdir_to_mimic_deletion():
    logging.warning('MOVING %s TO %s', de_src(original), copied)
    original.rename(copied)

  return CujGroup(de_src(original), [
      CujStep('delete',
              move_to_tempdir_to_mimic_deletion,
              InWorkspace.OMISSION.verifier(original)),
      CujStep('restore',
              lambda: copied.rename(original),
              ws.verifier(original))
  ])


def replace_link_with_dir(p: Path):
  """Create a file, replace it with a non-empty directory, delete it"""
  cd = create_delete(p, InWorkspace.SYMLINK)
  create_file: CujStep
  delete_file: CujStep
  create_file, delete_file, *tail = cd.steps
  assert len(tail) == 0

  # an Android.bp is always a symlink in the workspace and thus its parent
  # will be a directory in the workspace
  create_dir: CujStep
  delete_dir: CujStep
  create_dir, delete_dir, *tail = create_delete_bp(
      p.joinpath('Android.bp')).steps
  assert len(tail) == 0

  def replace_it():
    delete_file.apply_change()
    create_dir.apply_change()

  return CujGroup(cd.description, [
      create_file,
      CujStep(f'{de_src(p)}/Android.bp instead of',
              replace_it,
              create_dir.verify),
      delete_dir
  ])


def _sequence(*vs: Verifier) -> Verifier:
  def f():
    for v in vs:
      v()

  return f


def content_verfiers(
    ws_build_file: Path, content: str) -> (Verifier, Verifier):
  def search() -> bool:
    with open(ws_build_file, "r") as f:
      for line in f:
        if line == content:
          return True
    return False

  @skip_when_soong_only
  def contains():
    if not search():
      raise AssertionError(
          f'{de_src(ws_build_file)} expected to contain {content}')
    logging.info(f'VERIFIED {de_src(ws_build_file)} contains {content}')

  @skip_when_soong_only
  def does_not_contain():
    if search():
      raise AssertionError(
          f'{de_src(ws_build_file)} not expected to contain {content}')
    logging.info(f'VERIFIED {de_src(ws_build_file)} does not contain {content}')

  return contains, does_not_contain


def modify_revert_kept_build_file(build_file: Path) -> CujGroup:
  content = f'//BOGUS {uuid.uuid4()}\n'
  step1, step2, *tail = modify_revert(build_file, content).steps
  assert len(tail) == 0
  ws_build_file = InWorkspace.ws_counterpart(build_file).with_name(
      'BUILD.bazel')
  merge_prover, merge_disprover = content_verfiers(ws_build_file, content)
  return CujGroup(de_src(build_file), [
      CujStep(step1.verb,
              step1.apply_change,
              _sequence(step1.verify, merge_prover)),
      CujStep(step2.verb,
              step2.apply_change,
              _sequence(step2.verify, merge_disprover))
  ])


def create_delete_kept_build_file(build_file: Path) -> CujGroup:
  content = f'//BOGUS {uuid.uuid4()}\n'
  ws_build_file = InWorkspace.ws_counterpart(build_file).with_name(
      'BUILD.bazel')
  if build_file.name == 'BUILD.bazel':
    ws = InWorkspace.NOT_UNDER_SYMLINK
  elif build_file.name == 'BUILD':
    ws = InWorkspace.SYMLINK
  else:
    raise RuntimeError(f'Illegal name for a build file {build_file}')

  merge_prover, merge_disprover = content_verfiers(ws_build_file, content)

  step1: CujStep
  step2: CujStep
  step1, step2, *tail = create_delete(build_file, ws, content).steps
  assert len(tail) == 0
  return CujGroup(de_src(build_file), [
      CujStep(step1.verb,
              step1.apply_change,
              _sequence(step1.verify, merge_prover)),
      CujStep(step2.verb,
              step2.apply_change,
              _sequence(step2.verify, merge_disprover))
  ])


def create_delete_unkept_build_file(build_file) -> CujGroup:
  content = f'//BOGUS {uuid.uuid4()}\n'
  ws_build_file = InWorkspace.ws_counterpart(build_file).with_name(
      'BUILD.bazel')
  step1: CujStep
  step2: CujStep
  step1, step2, *tail = create_delete(
      build_file, InWorkspace.SYMLINK, content).steps
  assert len(tail) == 0
  _, merge_disprover = content_verfiers(ws_build_file, content)
  return CujGroup(de_src(build_file), [
      CujStep(step1.verb,
              step1.apply_change,
              _sequence(step1.verify, merge_disprover)),
      CujStep(step2.verb,
              step2.apply_change,
              _sequence(step2.verify, merge_disprover))
  ])


NON_LEAF = '*/*'
"""If `a/*/*` is a valid path `a` is not a leaf directory"""
LEAF = '!*/*'
"""If `a/*/*` is not a valid path `a` is a leaf directory, i.e. has no other
non-empty sub-directories"""
PKG = ['Android.bp', '!BUILD', '!BUILD.bazel']
"""limiting the candidate to Android.bp file with no sibling bazel files"""
PKG_FREE = ['!**/Android.bp', '!**/BUILD', '!**/BUILD.bazel']
"""no Android.bp or BUILD or BUILD.bazel file anywhere"""


def _kept_build_cujs() -> list[CujGroup]:
  # Bp2BuildKeepExistingBuildFile(build/bazel) is True(recursive)
  kept = src('build/bazel')
  pkg = util.any_dir_under(kept, *PKG)
  examples = [pkg.joinpath('BUILD'),
              pkg.joinpath('BUILD.bazel')]

  return [
      *[create_delete_kept_build_file(build_file) for build_file in examples],
      create_delete(pkg.joinpath('BUILD/kept-dir'), InWorkspace.SYMLINK),
      modify_revert_kept_build_file(util.any_file_under(kept, 'BUILD'))]


def _unkept_build_cujs() -> list[CujGroup]:
  # Bp2BuildKeepExistingBuildFile(bionic) is False(recursive)
  unkept = src('bionic')
  pkg = util.any_dir_under(unkept, *PKG)
  return [
      *[create_delete_unkept_build_file(build_file) for build_file in [
          pkg.joinpath('BUILD'),
          pkg.joinpath('BUILD.bazel'),
      ]],
      *[create_delete(build_file, InWorkspace.OMISSION) for build_file in [
          unkept.joinpath('bogus-unkept/BUILD'),
          unkept.joinpath('bogus-unkept/BUILD.bazel'),
      ]],
      create_delete(pkg.joinpath('BUILD/unkept-dir'), InWorkspace.SYMLINK)
  ]


@functools.cache
def get_cujgroups() -> list[CujGroup]:
  # we are choosing "package" directories that have Android.bp but
  # not BUILD nor BUILD.bazel because
  # we can't tell if ShouldKeepExistingBuildFile would be True or not
  pkg, p_why = util.any_match(NON_LEAF, *PKG)
  pkg_free, f_why = util.any_match(NON_LEAF, *PKG_FREE)
  leaf_pkg_free, _ = util.any_match(LEAF, *PKG_FREE)
  ancestor, a_why = util.any_match('!Android.bp', '!BUILD', '!BUILD.bazel',
                                   '**/Android.bp')
  logging.info(textwrap.dedent(f'''Choosing:
            package: {de_src(pkg)} has {p_why}
   package ancestor: {de_src(ancestor)} has {a_why} but no direct Android.bp
       package free: {de_src(pkg_free)} has {f_why} but no Android.bp anywhere
  leaf package free: {de_src(leaf_pkg_free)} has neither Android.bp nor sub-dirs
  '''))

  android_bp_cujs = [
      modify_revert(src('Android.bp')),
      *[create_delete_bp(d.joinpath('Android.bp')) for d in
        [ancestor, pkg_free, leaf_pkg_free]]
  ]
  mixed_build_launch_cujs = [
      modify_revert(src('bionic/libc/tzcode/asctime.c')),
      modify_revert(src('bionic/libc/stdio/stdio.cpp')),
      modify_revert(src('packages/modules/adb/daemon/main.cpp')),
      modify_revert(src('frameworks/base/core/java/android/view/View.java')),
  ]
  unreferenced_file_cujs = [
      *[create_delete(d.joinpath('unreferenced.txt'), InWorkspace.SYMLINK) for
        d in [ancestor, pkg]],
      *[create_delete(d.joinpath('unreferenced.txt'), InWorkspace.UNDER_SYMLINK)
        for d
        in [pkg_free, leaf_pkg_free]]
  ]

  def clean():
    if ui.get_user_input().log_dir.is_relative_to(util.get_top_dir()):
      raise AssertionError(
          f'specify a different LOG_DIR: {ui.get_user_input().log_dir}')
    if util.get_out_dir().exists():
      shutil.rmtree(util.get_out_dir())

  return [
      CujGroup('', [CujStep('clean', clean)]),
      CujGroup('', Warmup.steps),
      clone.get_cuj_group(
          src('packages/modules/adb/Android.bp'), 'adbd'),
      clone.get_cuj_group(
          src('packages/modules/NeuralNetworks/runtime/Android.bp'),
          'libneuralnetworks'),

      create_delete(src('bionic/libc/tzcode/globbed.c'),
                    InWorkspace.UNDER_SYMLINK),

      # TODO (usta): find targets that should be affected
      *[delete_restore(f, InWorkspace.SYMLINK) for f in [
          util.any_file('version_script.txt'),
          util.any_file('AndroidManifest.xml')]],

      *unreferenced_file_cujs,
      *mixed_build_launch_cujs,
      *android_bp_cujs,
      *_unkept_build_cujs(),
      *_kept_build_cujs(),
      replace_link_with_dir(pkg.joinpath('bogus.txt')),
      # TODO(usta): add a dangling symlink
  ]

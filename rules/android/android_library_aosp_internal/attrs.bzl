"""
Copyright (C) 2023 The Android Open Source Project

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

load(
    "@rules_android//rules:attrs.bzl",
    _attrs = "attrs",
)
load(
    "@rules_android//rules/android_library:attrs.bzl",
    _BASE_ATTRS = "ATTRS",
)
load("@rules_kotlin//kotlin:compiler_opt.bzl", "kotlincopts_attrs")
load("@rules_kotlin//kotlin:traverse_exports.bzl", _kt_traverse_exports = "kt_traverse_exports")

_KT_COMPILER_ATTRS = _attrs.add(
    kotlincopts_attrs(),
    dict(
        common_srcs = attr.label_list(
            allow_files = [".kt"],
            doc = """The list of common multi-platform source files that are processed to create
                 the target.""",
        ),
        coverage_srcs = attr.label_list(allow_files = True),
        # Magic attribute name for DexArchiveAspect
        _toolchain = attr.label(
            default = Label(
                "//build/bazel/rules/kotlin:kt_jvm_toolchain_linux_jdk",
            ),
        ),
    ),
)

ATTRS = _attrs.add(
    _attrs.replace(
        _BASE_ATTRS,
        deps = attr.label_list(
            allow_rules = [
                "aar_import",
                "android_library",
                "cc_library",
                "java_import",
                "java_library",
                "java_lite_proto_library",
            ],
            aspects = [
                _kt_traverse_exports.aspect,
            ],
            providers = [
                [CcInfo],
                [JavaInfo],
            ],
            doc = (
                "The list of other libraries to link against. Permitted library types " +
                "are: `android_library`, `java_library` with `android` constraint and " +
                "`cc_library` wrapping or producing `.so` native libraries for the " +
                "Android target platform."
            ),
        ),
        exported_plugins = attr.label_list(
            allow_rules = [
                "java_plugin",
            ],
            cfg = "exec",
        ),
        exports = attr.label_list(
            allow_rules = [
                "aar_import",
                "android_library",
                "cc_library",
                "java_import",
                "java_library",
                "java_lite_proto_library",
            ],
            aspects = [
                _kt_traverse_exports.aspect,
            ],
            providers = [
                [CcInfo],
                [JavaInfo],
            ],
            doc = (
                "The closure of all rules reached via `exports` attributes are considered " +
                "direct dependencies of any rule that directly depends on the target with " +
                "`exports`. The `exports` are not direct deps of the rule they belong to."
            ),
        ),
        exports_manifest = _attrs.tristate.create(
            default = _attrs.tristate.no,
            doc = (
                "Whether to export manifest entries to `android_binary` targets that " +
                "depend on this target. `uses-permissions` attributes are never exported."
            ),
        ),
        plugins = attr.label_list(
            providers = [
                [JavaPluginInfo],
            ],
            cfg = "exec",
            doc = (
                "Java compiler plugins to run at compile-time. Every `java_plugin` " +
                "specified in the plugins attribute will be run whenever this target " +
                "is built. Resources generated by the plugin will be included in " +
                "the result jar of the target."
            ),
        ),
        srcs = attr.label_list(
            allow_files = [
                ".kt",
                ".java",
                ".srcjar",
            ],
        ),
    ),
    _KT_COMPILER_ATTRS,
)

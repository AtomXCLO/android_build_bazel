#!/bin/bash -eu

# Copyright (C) 2023 The Android Open Source Project
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

# Verifies that the b invocations properly record metrics and their exit codes.
build/bazel/bin/b build libcore:all

build/bazel/scripts/analyze_build

if [[ ! $(grep '"exitCode": 0' out/analyze_build_output/bazel_metrics.json) ]]; then
   echo "Failed to locate bazel exit code in metrics output"
   exit 1
fi

build/bazel/bin/b build libcore:nonexistent_module || true

build/bazel/scripts/analyze_build

if [[ ! $(grep '"exitCode": 1' out/analyze_build_output/bazel_metrics.json) ]]; then
   echo "Failed to locate bazel exit code in metrics output"
   exit 1
fi

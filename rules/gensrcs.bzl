"""
Copyright (C) 2021 The Android Open Source Project

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

load("@bazel_skylib//lib:paths.bzl", "paths")

# A rule to generate files based on provided srcs and tools
def _gensrcs_impl(ctx):
    # The next two assignments can be created by using ctx.resolve_command
    # TODO: Switch to using ctx.resolve_command when it is out of experimental
    command = ctx.expand_location(ctx.attr.cmd)
    tools = [
        tool[DefaultInfo].files_to_run
        for tool in ctx.attr.tools
    ]

    out_files = []
    for in_file in ctx.files.srcs:
        out_file = ctx.actions.declare_file(
            paths.replace_extension(
                in_file.basename,
                "." + ctx.attr.output_extension,
            ),
            sibling = in_file,
        )
        shell_command = command \
            .replace("$(SRC)", in_file.path) \
            .replace("$(OUT)", out_file.path)
        ctx.actions.run_shell(
            tools = tools,
            outputs = [out_file],
            inputs = [in_file],
            command = shell_command,
            progress_message = "Generating %s from %s" % (
                out_file.path,
                in_file.path,
            ),
        )
        out_files.append(out_file)

    return [DefaultInfo(
        files = depset(out_files),
    )]

gensrcs = rule(
    implementation = _gensrcs_impl,
    doc = "This rule generates files, where each of the `srcs` files is " +
          "passed into the custom shell command`",
    attrs = {
        "srcs": attr.label_list(
            allow_files = True,
            mandatory = True,
            doc = "A list of inputs such as source files to process",
        ),
        "output_extension": attr.string(
            mandatory = True,
            doc = "The extension that will be substituted for output files",
        ),
        "cmd": attr.string(
            mandatory = True,
            doc = "The command to run. Subject to $(location) expansion. " +
                  "$(IN) represents each input file provided in `srcs` " +
                  "while $(OUT) reprensents corresponding output file " +
                  "generated by the rule",
        ),
        "tools": attr.label_list(
            allow_files = True,
            doc = "A list of tool dependencies for this rule. " +
                  "The path of an individual `tools` target //x:y can be " +
                  "obtained using `$(location //x:y)`",
        ),
    },
)

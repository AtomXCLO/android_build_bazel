load("@bazel_skylib//lib:unittest.bzl", "asserts", "unittest")
load("//build/bazel/rules/common:api.bzl", "api")

def _api_levels_test_impl(ctx):
    env = unittest.begin(ctx)

    # schema: version string to parse: expected api int
    _LEVELS_UNDER_TEST = {
        # numbers
        "9": 9,  # earliest released number
        "21": 21,
        "30": 30,
        "33": 33,
        # unchecked non final api level (not finalized, not preview, not current)
        "1234": 1234,
        "8999": 8999,
        "9999": 9999,
        "10001": 10001,
        # letters
        "G": 9,  # earliest released letter
        "J-MR1": 17,
        "R": 30,
        "S": 31,
        "S-V2": 32,
        # codenames
        "Tiramisu": 33,
        "UpsideDownCake": 9000,
        "current": 10000,
        "9000": 9000,
        "10000": 10000,
    }

    for level, expected in _LEVELS_UNDER_TEST.items():
        asserts.equals(env, expected, api.parse_api_level_from_version(level), "unexpected api level parsed for %s" % level)

    return unittest.end(env)

api_levels_test = unittest.make(_api_levels_test_impl)

def _final_or_future_test_impl(ctx):
    env = unittest.begin(ctx)

    # schema: version string to parse: expected api int
    _LEVELS_UNDER_TEST = {
        # finalized
        "30": 30,
        "33": 33,
        "S": 31,
        "S-V2": 32,
        "Tiramisu": 33,
        # not finalized
        "UpsideDownCake": 10000,
        "current": 10000,
        "9000": 10000,
        "10000": 10000,
    }

    for level, expected in _LEVELS_UNDER_TEST.items():
        asserts.equals(
            env,
            expected,
            api.final_or_future(api.parse_api_level_from_version(level)),
            "unexpected final or future api for %s" % level,
        )

    return unittest.end(env)

final_or_future_test = unittest.make(_final_or_future_test_impl)

def api_levels_test_suite(name):
    unittest.suite(
        name,
        api_levels_test,
        final_or_future_test,
    )

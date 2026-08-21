"""Conan recipe for the sensorcore library.

The version is not hardcoded: it is injected by the build (`scripts/version.sh`
-> `--version=` on the command line, or the SENSORCORE_VERSION environment
variable) so that the Conan package, the DEB, the wheel and the Docker tag all
carry the exact same string.
"""

import os

from conan import ConanFile
from conan.tools.build import check_min_cppstd
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.files import copy


class SensorcoreConan(ConanFile):
    name = "sensorcore"
    license = "MIT"
    url = "https://github.com/bulbashenko/pet-devops"
    description = "Deterministic sensor telemetry simulation and aggregation library"
    topics = ("telemetry", "sensors", "simulation")

    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = {"shared": False, "fPIC": True}

    exports_sources = "CMakeLists.txt", "include/*", "src/*", "test/*"

    def set_version(self):
        self.version = self.version or os.environ.get("SENSORCORE_VERSION", "0.0.0")

    def requirements(self):
        self.requires("fmt/10.2.1", transitive_headers=True)

    def build_requirements(self):
        self.test_requires("gtest/1.14.0")

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")

    def validate(self):
        check_min_cppstd(self, 17)

    def layout(self):
        cmake_layout(self)

    def generate(self):
        deps = CMakeDeps(self)
        deps.generate()
        tc = CMakeToolchain(self)
        tc.variables["SENSORCORE_VERSION"] = self.version
        tc.variables["SENSORCORE_BUILD_TESTS"] = not self.conf.get(
            "tools.build:skip_test", default=False, check_type=bool
        )
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
        if not self.conf.get("tools.build:skip_test", default=False, check_type=bool):
            cmake.ctest(cli_args=["--output-on-failure"])

    def package(self):
        cmake = CMake(self)
        cmake.install()
        copy(
            self,
            "LICENSE",
            src=os.path.join(self.recipe_folder, "..", ".."),
            dst=os.path.join(self.package_folder, "licenses"),
        )

    def package_info(self):
        self.cpp_info.libs = ["sensorcore"]
        self.cpp_info.set_property("cmake_target_name", "sensorcore::sensorcore")
        self.cpp_info.set_property("cmake_file_name", "sensorcore")

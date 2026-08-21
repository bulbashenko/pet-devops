"""Conan recipe for the sensor-hub daemon.

This one *consumes* sensorcore (from the internal Artifactory remote) alongside
third-party packages from conancenter — the other half of the packaging story
that the sensorcore recipe demonstrates.
"""

import os

from conan import ConanFile
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout


class SensorHubConan(ConanFile):
    name = "sensor-hub"
    license = "MIT"
    url = "https://github.com/bulbashenko/pet-devops"
    description = "HTTP daemon exposing simulated sensor telemetry"
    package_type = "application"

    settings = "os", "compiler", "build_type", "arch"
    exports_sources = "CMakeLists.txt", "src/*"

    def set_version(self):
        self.version = self.version or os.environ.get("SENSORCORE_VERSION", "0.0.0")

    def requirements(self):
        self.requires(f"sensorcore/{self.version}")
        self.requires("fmt/10.2.1")
        self.requires("cpp-httplib/0.15.3")
        self.requires("nlohmann_json/3.11.3")

    def layout(self):
        cmake_layout(self)

    def generate(self):
        deps = CMakeDeps(self)
        deps.generate()
        tc = CMakeToolchain(self)
        tc.variables["SENSORCORE_VERSION"] = self.version
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()

    def package_info(self):
        self.cpp_info.bindirs = ["bin"]

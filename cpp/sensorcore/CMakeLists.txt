cmake_minimum_required(VERSION 3.22)

# project() has to run before the version handling: on a first configure the
# Conan toolchain (which carries SENSORCORE_VERSION) is only loaded as part of
# project() itself.
project(sensorcore LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(SENSORCORE_BUILD_TESTS "Build sensorcore unit tests" ON)

# The full version string (e.g. 0.3.1.dev4+g1a2b3c4) is what gets reported over
# the API; CMake's own VERSION/SOVERSION properties only accept numbers, so the
# numeric prefix is extracted for them. See scripts/version.sh.
if(NOT DEFINED SENSORCORE_VERSION OR SENSORCORE_VERSION STREQUAL "")
  set(SENSORCORE_VERSION "0.0.0")
endif()
string(REGEX MATCH "^[0-9]+\\.[0-9]+\\.[0-9]+" SENSORCORE_VERSION_NUMERIC "${SENSORCORE_VERSION}")
if(NOT SENSORCORE_VERSION_NUMERIC)
  set(SENSORCORE_VERSION_NUMERIC "0.0.0")
endif()
string(REGEX MATCH "^[0-9]+" SENSORCORE_VERSION_MAJOR "${SENSORCORE_VERSION_NUMERIC}")
message(STATUS "sensorcore version: ${SENSORCORE_VERSION} (abi ${SENSORCORE_VERSION_NUMERIC})")

find_package(fmt REQUIRED)

configure_file(include/sensorcore/version.hpp.in
               ${CMAKE_CURRENT_BINARY_DIR}/generated/sensorcore/version.hpp @ONLY)

add_library(sensorcore
  src/reading.cpp
  src/simulator.cpp
  src/stats.cpp
)
add_library(sensorcore::sensorcore ALIAS sensorcore)

target_include_directories(sensorcore
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}/generated>
    $<INSTALL_INTERFACE:include>
)
target_link_libraries(sensorcore PUBLIC fmt::fmt)
target_compile_options(sensorcore PRIVATE -Wall -Wextra -Wpedantic)

set_target_properties(sensorcore PROPERTIES
  VERSION ${SENSORCORE_VERSION_NUMERIC}
  SOVERSION ${SENSORCORE_VERSION_MAJOR}
)

if(SENSORCORE_BUILD_TESTS)
  find_package(GTest REQUIRED)
  enable_testing()
  include(GoogleTest)

  add_executable(sensorcore_tests test/test_stats.cpp test/test_simulator.cpp)
  target_link_libraries(sensorcore_tests PRIVATE sensorcore GTest::gtest_main)
  gtest_discover_tests(sensorcore_tests)
endif()

install(TARGETS sensorcore EXPORT sensorcoreTargets
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)
install(DIRECTORY include/sensorcore DESTINATION include
        FILES_MATCHING PATTERN "*.hpp")
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/generated/sensorcore/version.hpp
        DESTINATION include/sensorcore)

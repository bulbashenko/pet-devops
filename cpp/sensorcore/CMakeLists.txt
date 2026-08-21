cmake_minimum_required(VERSION 3.22)

# Version comes from scripts/version.sh (git tag). Standalone builds without a
# tag still work — they just get 0.0.0.
if(NOT DEFINED SENSORCORE_VERSION)
  set(SENSORCORE_VERSION "0.0.0")
endif()

project(sensorcore VERSION ${SENSORCORE_VERSION} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(SENSORCORE_BUILD_TESTS "Build sensorcore unit tests" ON)

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
  VERSION ${PROJECT_VERSION}
  SOVERSION ${PROJECT_VERSION_MAJOR}
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

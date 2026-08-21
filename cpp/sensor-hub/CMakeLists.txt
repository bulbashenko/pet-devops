cmake_minimum_required(VERSION 3.22)

project(sensor-hub LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(sensorcore REQUIRED)
find_package(fmt REQUIRED)
find_package(httplib REQUIRED)
find_package(nlohmann_json REQUIRED)

add_executable(sensor-hub src/main.cpp src/config.cpp)
target_link_libraries(sensor-hub
  PRIVATE
    sensorcore::sensorcore
    fmt::fmt
    httplib::httplib
    nlohmann_json::nlohmann_json
)
target_compile_options(sensor-hub PRIVATE -Wall -Wextra -Wpedantic)

install(TARGETS sensor-hub RUNTIME DESTINATION bin)

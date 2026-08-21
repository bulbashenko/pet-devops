#pragma once

#include <cstdint>
#include <string>

namespace sensorcore {

/// A single measurement taken from one sensor channel.
struct Reading {
    std::string sensor_id;
    std::int64_t timestamp_ms{0};
    double value{0.0};
    std::string unit;
};

/// Human-readable one-line rendering, used by logs and the CLI.
std::string to_string(const Reading& reading);

}  // namespace sensorcore

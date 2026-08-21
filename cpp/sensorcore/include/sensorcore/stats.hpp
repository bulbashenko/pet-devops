#pragma once

#include <cstddef>
#include <map>
#include <string>
#include <vector>

#include "sensorcore/reading.hpp"

namespace sensorcore {

/// Summary of a set of readings from a single channel.
struct Stats {
    std::size_t count{0};
    double min{0.0};
    double max{0.0};
    double mean{0.0};
    double stddev{0.0};
};

/// Aggregates readings regardless of which channel they came from.
/// An empty input yields a zeroed Stats with count == 0.
Stats aggregate(const std::vector<Reading>& readings);

/// Aggregates readings grouped by `sensor_id`.
std::map<std::string, Stats> aggregate_by_sensor(const std::vector<Reading>& readings);

}  // namespace sensorcore

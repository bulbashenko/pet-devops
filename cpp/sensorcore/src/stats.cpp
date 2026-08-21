#include "sensorcore/stats.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>

namespace sensorcore {

Stats aggregate(const std::vector<Reading>& readings) {
    Stats stats;
    if (readings.empty()) {
        return stats;
    }

    stats.count = readings.size();
    stats.min = readings.front().value;
    stats.max = readings.front().value;

    double sum = 0.0;
    for (const auto& reading : readings) {
        stats.min = std::min(stats.min, reading.value);
        stats.max = std::max(stats.max, reading.value);
        sum += reading.value;
    }
    stats.mean = sum / static_cast<double>(stats.count);

    double sum_sq = 0.0;
    for (const auto& reading : readings) {
        const double delta = reading.value - stats.mean;
        sum_sq += delta * delta;
    }
    stats.stddev = std::sqrt(sum_sq / static_cast<double>(stats.count));

    return stats;
}

std::map<std::string, Stats> aggregate_by_sensor(const std::vector<Reading>& readings) {
    std::map<std::string, std::vector<Reading>> grouped;
    for (const auto& reading : readings) {
        grouped[reading.sensor_id].push_back(reading);
    }

    std::map<std::string, Stats> result;
    for (const auto& [sensor_id, group] : grouped) {
        result[sensor_id] = aggregate(group);
    }
    return result;
}

}  // namespace sensorcore

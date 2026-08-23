#pragma once

#include <cstdint>
#include <random>
#include <string>
#include <vector>

#include "sensorcore/reading.hpp"

namespace sensorcore {

/// Description of one simulated sensor channel.
struct ChannelSpec {
    std::string sensor_id;
    std::string unit;
    double baseline{0.0};
    double amplitude{1.0};
};

/// Deterministic telemetry source.
///
/// The same seed always yields the same sequence of readings, which is what
/// makes the integration and smoke tests assertable rather than flaky.
class Simulator {
public:
    Simulator(std::vector<ChannelSpec> channels, std::uint64_t seed);

    /// Advances the simulation by one step and returns one reading per channel.
    std::vector<Reading> step(std::int64_t timestamp_ms);

    /// Convenience wrapper producing `count` steps spaced `interval_ms` apart.
    std::vector<Reading> sample(std::size_t count, std::int64_t interval_ms,
                                std::int64_t start_ms = 0);

    const std::vector<ChannelSpec>& channels() const noexcept { return channels_; }

private:
    std::vector<ChannelSpec> channels_;
    std::mt19937_64 engine_;
    std::uint64_t tick_{0};
};

/// The channel set the daemon ships with by default.
std::vector<ChannelSpec> default_channels();

}  // namespace sensorcore

#include "sensorcore/simulator.hpp"

#include <cmath>
#include <utility>

namespace sensorcore {
namespace {

constexpr double kTwoPi = 6.283185307179586;
constexpr double kPeriodTicks = 32.0;

}  // namespace

Simulator::Simulator(std::vector<ChannelSpec> channels, std::uint64_t seed)
    : channels_(std::move(channels)), engine_(seed) {}

std::vector<Reading> Simulator::step(std::int64_t timestamp_ms) {
    // A slow sine carries the signal so values look like telemetry rather than
    // noise; the seeded engine adds jitter without breaking reproducibility.
    std::uniform_real_distribution<double> jitter(-0.05, 0.05);
    const double phase = kTwoPi * static_cast<double>(tick_) / kPeriodTicks;

    std::vector<Reading> readings;
    readings.reserve(channels_.size());
    for (const auto& channel : channels_) {
        const double value =
            channel.baseline + channel.amplitude * (std::sin(phase) + jitter(engine_));
        readings.push_back(Reading{channel.sensor_id, timestamp_ms, value, channel.unit});
    }

    ++tick_;
    return readings;
}

std::vector<Reading> Simulator::sample(std::size_t count, std::int64_t interval_ms,
                                       std::int64_t start_ms) {
    std::vector<Reading> readings;
    readings.reserve(count * channels_.size());
    for (std::size_t i = 0; i < count; ++i) {
        auto batch = step(start_ms + static_cast<std::int64_t>(i) * interval_ms);
        readings.insert(readings.end(), batch.begin(), batch.end());
    }
    return readings;
}

std::vector<ChannelSpec> default_channels() {
    return {
        ChannelSpec{"temp-01", "C", 21.5, 3.0},
        ChannelSpec{"humidity-01", "%", 45.0, 8.0},
        ChannelSpec{"imu-01-accel-z", "m/s2", 9.81, 0.4},
    };
}

}  // namespace sensorcore

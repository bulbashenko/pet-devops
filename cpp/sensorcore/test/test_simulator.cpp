#include <gtest/gtest.h>

#include "sensorcore/simulator.hpp"
#include "sensorcore/stats.hpp"

namespace {

std::vector<sensorcore::ChannelSpec> one_channel() {
    return {sensorcore::ChannelSpec{"temp-01", "C", 20.0, 2.0}};
}

TEST(Simulator, SameSeedProducesSameSequence) {
    sensorcore::Simulator a(one_channel(), 42);
    sensorcore::Simulator b(one_channel(), 42);

    const auto left = a.sample(16, 100);
    const auto right = b.sample(16, 100);

    ASSERT_EQ(left.size(), right.size());
    for (std::size_t i = 0; i < left.size(); ++i) {
        EXPECT_DOUBLE_EQ(left[i].value, right[i].value) << "diverged at index " << i;
    }
}

TEST(Simulator, DifferentSeedsDiverge) {
    sensorcore::Simulator a(one_channel(), 1);
    sensorcore::Simulator b(one_channel(), 2);
    EXPECT_NE(a.sample(8, 100).front().value, b.sample(8, 100).front().value);
}

TEST(Simulator, EmitsOneReadingPerChannelPerStep) {
    sensorcore::Simulator sim(sensorcore::default_channels(), 7);
    const auto channels = sensorcore::default_channels().size();

    EXPECT_EQ(sim.step(0).size(), channels);
    EXPECT_EQ(sim.sample(5, 10).size(), 5 * channels);
}

TEST(Simulator, TimestampsAdvanceByInterval) {
    sensorcore::Simulator sim(one_channel(), 3);
    const auto readings = sim.sample(4, 250, 1000);

    ASSERT_EQ(readings.size(), 4u);
    EXPECT_EQ(readings[0].timestamp_ms, 1000);
    EXPECT_EQ(readings[3].timestamp_ms, 1750);
}

TEST(Simulator, ValuesStayWithinBaselinePlusAmplitudeBand) {
    sensorcore::Simulator sim(one_channel(), 11);
    const auto stats = sensorcore::aggregate(sim.sample(200, 10));

    // sin() in [-1, 1] plus jitter in [-0.05, 0.05], scaled by amplitude 2.0.
    EXPECT_GE(stats.min, 20.0 - 2.0 * 1.05);
    EXPECT_LE(stats.max, 20.0 + 2.0 * 1.05);
}

}  // namespace

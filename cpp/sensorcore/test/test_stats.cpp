#include <gtest/gtest.h>

#include "sensorcore/stats.hpp"

namespace {

sensorcore::Reading make(const std::string& id, double value) {
    return sensorcore::Reading{id, 0, value, "C"};
}

TEST(Stats, EmptyInputYieldsZeroCount) {
    const auto stats = sensorcore::aggregate({});
    EXPECT_EQ(stats.count, 0u);
    EXPECT_DOUBLE_EQ(stats.mean, 0.0);
}

TEST(Stats, SingleValueHasZeroSpread) {
    const auto stats = sensorcore::aggregate({make("a", 4.0)});
    EXPECT_EQ(stats.count, 1u);
    EXPECT_DOUBLE_EQ(stats.min, 4.0);
    EXPECT_DOUBLE_EQ(stats.max, 4.0);
    EXPECT_DOUBLE_EQ(stats.mean, 4.0);
    EXPECT_DOUBLE_EQ(stats.stddev, 0.0);
}

TEST(Stats, ComputesMinMaxMeanStddev) {
    const auto stats = sensorcore::aggregate({make("a", 2.0), make("a", 4.0), make("a", 4.0),
                                              make("a", 4.0), make("a", 5.0), make("a", 5.0),
                                              make("a", 7.0), make("a", 9.0)});
    EXPECT_EQ(stats.count, 8u);
    EXPECT_DOUBLE_EQ(stats.min, 2.0);
    EXPECT_DOUBLE_EQ(stats.max, 9.0);
    EXPECT_DOUBLE_EQ(stats.mean, 5.0);
    EXPECT_DOUBLE_EQ(stats.stddev, 2.0);
}

TEST(Stats, GroupsBySensorId) {
    const auto grouped = sensorcore::aggregate_by_sensor(
        {make("a", 1.0), make("b", 10.0), make("a", 3.0), make("b", 20.0)});

    ASSERT_EQ(grouped.size(), 2u);
    EXPECT_DOUBLE_EQ(grouped.at("a").mean, 2.0);
    EXPECT_DOUBLE_EQ(grouped.at("b").mean, 15.0);
}

}  // namespace

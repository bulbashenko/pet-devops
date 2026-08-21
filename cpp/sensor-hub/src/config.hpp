#pragma once

#include <cstdint>
#include <string>

namespace sensorhub {

struct Config {
    std::string host{"0.0.0.0"};
    int port{8080};
    std::uint64_t seed{42};
    std::int64_t interval_ms{100};
};

/// Reads a minimal `key: value` config file (the subset of YAML the shipped
/// /etc/sensor-hub/config.yaml uses). Missing file -> defaults, which keeps the
/// container image runnable without a mounted config.
Config load_config(const std::string& path);

/// Environment overrides (SENSOR_HUB_PORT, SENSOR_HUB_SEED, ...) win over the
/// file so the compose stack can retarget a container without a rebuild.
void apply_env_overrides(Config& config);

}  // namespace sensorhub

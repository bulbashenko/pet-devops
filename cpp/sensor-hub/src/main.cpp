#include <fmt/format.h>
#include <httplib.h>

#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <nlohmann/json.hpp>
#include <string>

#include "config.hpp"
#include "sensorcore/simulator.hpp"
#include "sensorcore/stats.hpp"
#include "sensorcore/version.hpp"

namespace {

using nlohmann::json;

httplib::Server* g_server = nullptr;

void handle_signal(int) {
    if (g_server != nullptr) {
        g_server->stop();
    }
}

std::int64_t now_ms() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
               std::chrono::system_clock::now().time_since_epoch())
        .count();
}

json to_json(const sensorcore::Reading& reading) {
    return json{{"sensor_id", reading.sensor_id},
                {"timestamp_ms", reading.timestamp_ms},
                {"value", reading.value},
                {"unit", reading.unit}};
}

json to_json(const sensorcore::Stats& stats) {
    return json{{"count", stats.count},
                {"min", stats.min},
                {"max", stats.max},
                {"mean", stats.mean},
                {"stddev", stats.stddev}};
}

/// Clamps ?n= to a sane range so a stray `?n=100000000` cannot exhaust memory.
std::size_t parse_count(const httplib::Request& request) {
    constexpr std::size_t kDefault = 10;
    constexpr std::size_t kMax = 1000;

    if (!request.has_param("n")) {
        return kDefault;
    }
    try {
        const auto requested = std::stoll(request.get_param_value("n"));
        if (requested <= 0) {
            return kDefault;
        }
        return std::min(static_cast<std::size_t>(requested), kMax);
    } catch (const std::exception&) {
        return kDefault;
    }
}

}  // namespace

int main(int argc, char** argv) {
    const std::string config_path =
        (argc > 1) ? argv[1] : "/etc/sensor-hub/config.yaml";

    auto config = sensorhub::load_config(config_path);
    sensorhub::apply_env_overrides(config);

    sensorcore::Simulator simulator(sensorcore::default_channels(), config.seed);
    httplib::Server server;
    g_server = &server;
    std::signal(SIGTERM, handle_signal);
    std::signal(SIGINT, handle_signal);

    server.Get("/healthz", [](const httplib::Request&, httplib::Response& response) {
        response.set_content(json{{"status", "ok"}, {"version", sensorcore::kVersion}}.dump(),
                             "application/json");
    });

    server.Get("/api/v1/readings", [&](const httplib::Request& request, httplib::Response& response) {
        const auto readings = simulator.sample(parse_count(request), config.interval_ms, now_ms());

        json items = json::array();
        for (const auto& reading : readings) {
            items.push_back(to_json(reading));
        }
        response.set_content(json{{"count", items.size()}, {"readings", items}}.dump(),
                             "application/json");
    });

    server.Get("/api/v1/stats", [&](const httplib::Request& request, httplib::Response& response) {
        const auto readings = simulator.sample(parse_count(request), config.interval_ms, now_ms());

        json per_sensor = json::object();
        for (const auto& [sensor_id, stats] : sensorcore::aggregate_by_sensor(readings)) {
            per_sensor[sensor_id] = to_json(stats);
        }
        response.set_content(
            json{{"overall", to_json(sensorcore::aggregate(readings))}, {"per_sensor", per_sensor}}
                .dump(),
            "application/json");
    });

    fmt::print("sensor-hub {} listening on {}:{} (config: {})\n", sensorcore::kVersion, config.host,
               config.port, config_path);
    std::fflush(stdout);

    if (!server.listen(config.host, config.port)) {
        fmt::print(stderr, "failed to bind {}:{}\n", config.host, config.port);
        return 1;
    }
    return 0;
}

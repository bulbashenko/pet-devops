#include "config.hpp"

#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>

namespace sensorhub {
namespace {

std::string trim(const std::string& text) {
    const auto first = text.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) {
        return {};
    }
    const auto last = text.find_last_not_of(" \t\r\n");
    return text.substr(first, last - first + 1);
}

std::string strip_quotes(const std::string& text) {
    if (text.size() >= 2 && (text.front() == '"' || text.front() == '\'') &&
        text.front() == text.back()) {
        return text.substr(1, text.size() - 2);
    }
    return text;
}

const char* env_or_null(const char* name) {
    const char* value = std::getenv(name);
    return (value != nullptr && *value != '\0') ? value : nullptr;
}

}  // namespace

Config load_config(const std::string& path) {
    Config config;

    std::ifstream file(path);
    if (!file) {
        return config;
    }

    std::string line;
    while (std::getline(file, line)) {
        const auto comment = line.find('#');
        if (comment != std::string::npos) {
            line = line.substr(0, comment);
        }

        const auto separator = line.find(':');
        if (separator == std::string::npos) {
            continue;
        }

        const std::string key = trim(line.substr(0, separator));
        const std::string value = strip_quotes(trim(line.substr(separator + 1)));
        if (key.empty() || value.empty()) {
            continue;
        }

        try {
            if (key == "host") {
                config.host = value;
            } else if (key == "port") {
                config.port = std::stoi(value);
            } else if (key == "seed") {
                config.seed = std::stoull(value);
            } else if (key == "interval_ms") {
                config.interval_ms = std::stoll(value);
            }
        } catch (const std::exception&) {
            // A malformed value keeps the default rather than killing the daemon
            // at startup — systemd restart loops are worse than one odd setting.
        }
    }

    return config;
}

void apply_env_overrides(Config& config) {
    if (const char* value = env_or_null("SENSOR_HUB_HOST")) {
        config.host = value;
    }
    try {
        if (const char* value = env_or_null("SENSOR_HUB_PORT")) {
            config.port = std::stoi(value);
        }
        if (const char* value = env_or_null("SENSOR_HUB_SEED")) {
            config.seed = std::stoull(value);
        }
        if (const char* value = env_or_null("SENSOR_HUB_INTERVAL_MS")) {
            config.interval_ms = std::stoll(value);
        }
    } catch (const std::exception&) {
        // Same reasoning as above.
    }
}

}  // namespace sensorhub

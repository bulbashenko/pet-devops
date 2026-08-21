#include "sensorcore/reading.hpp"

#include <fmt/format.h>

namespace sensorcore {

std::string to_string(const Reading& reading) {
    return fmt::format("{} t={}ms {:.3f}{}", reading.sensor_id, reading.timestamp_ms, reading.value,
                       reading.unit);
}

}  // namespace sensorcore

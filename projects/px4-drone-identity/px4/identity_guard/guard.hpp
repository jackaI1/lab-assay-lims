#pragma once
#include <cstdint>
#include <cmath>

// Shared by the native regression test and the real PX4 module.
struct Guard {
    int state{0}; // idle=0, active=1, failsafe=2
    int reason{0}; // timeout=1, identity=2, frame=3, policy=4, disconnect=5
    uint64_t last_pulse{0};

    // MAVLink COMMAND_LONG encodes even integer control flags as floats.
    static int decode(float value, int max_value) {
        if (!std::isfinite(value) || value < 1.f || value > max_value) { return 0; }
        const int code = static_cast<int>(std::round(value));
        return std::fabs(value - code) < 0.001f ? code : 0;
    }
    void signal(uint64_t now, bool armed, float operation, float why) {
        switch (decode(operation, 3)) {
        case 1: pulse(now); break;
        case 2: {
            const int decoded_reason = decode(why, 5);
            if (decoded_reason > 0) { reject(decoded_reason); }
            break;
        }
        case 3: reset(armed); break;
        default: break;
        }
    }
    void pulse(uint64_t now) {
        if (state != 2) { state = 1; last_pulse = now; }
    }
    void reject(int why) {
        if (state != 2) { state = 2; reason = why; }
    }
    void tick(uint64_t now) {
        if (state == 1 && now - last_pulse > 2000000) { reject(1); }
    }
    bool reset(bool armed) {
        if (armed) { return false; }
        state = 0; reason = 0; last_pulse = 0;
        return true;
    }
    bool landing_required(bool armed) const { return state == 2 && armed; }
};

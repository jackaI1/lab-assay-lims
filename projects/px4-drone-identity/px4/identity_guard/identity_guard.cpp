#include "guard.hpp"
#include <atomic>
#include <cmath>
#include <cstring>
#include <px4_platform_common/log.h>
#include <px4_platform_common/posix.h>
#include <px4_platform_common/tasks.h>
#include <drivers/drv_hrt.h>
#include <uORB/Publication.hpp>
#include <uORB/Subscription.hpp>
#include <uORB/topics/vehicle_command.h>
#include <uORB/topics/vehicle_status.h>
#include <uORB/topics/identity_status.h>
#include <uORB/topics/debug_key_value.h>

static std::atomic<bool> running{false};
static std::atomic<bool> stop_requested{false};

static int guard_run(int, char *[])
{
    Guard guard;
    uORB::Subscription commands{ORB_ID(vehicle_command)};
    uORB::Subscription status_sub{ORB_ID(vehicle_status)};
    uORB::Publication<vehicle_command_s> command_pub{ORB_ID(vehicle_command)};
    uORB::Publication<identity_status_s> status_pub{ORB_ID(identity_status)};
    uORB::Publication<debug_key_value_s> debug_pub{ORB_ID(debug_key_value)};
    vehicle_status_s status{};
    uint64_t last_land = 0;
    uint64_t last_report = 0;

    while (!stop_requested.load()) {
        const uint64_t now = hrt_absolute_time();
        status_sub.update(&status);
        const bool armed = status.arming_state == vehicle_status_s::ARMING_STATE_ARMED;
        vehicle_command_s incoming{};
        while (commands.update(&incoming)) {
            // This channel is private to the local companion. External clients
            // cannot send USER_1 through the role-filtering gateway.
            if (incoming.command == 31000 && incoming.source_system == 42 && incoming.source_component == 191) {
                guard.signal(now, armed, incoming.param1, incoming.param2);
            }
        }
        guard.tick(now);
        if (guard.landing_required(armed) && now - last_land > 1000000) {
            vehicle_command_s land{};
            land.timestamp = now;
            land.param5 = NAN;
            land.param6 = NAN;
            land.param7 = NAN;
            land.command = vehicle_command_s::VEHICLE_CMD_NAV_LAND;
            land.target_system = 1;
            land.target_component = 1;
            land.source_system = 1;
            land.source_component = 191;
            land.from_external = false;
            command_pub.publish(land);
            last_land = now;
            PX4_WARN("identity failsafe: land, reason=%d", guard.reason);
        }
        if (now - last_report > 200000) {
            identity_status_s report{};
            report.timestamp = now;
            report.last_authenticated_heartbeat = guard.last_pulse;
            report.state = guard.state;
            report.reason = guard.reason;
            report.armed = armed;
            status_pub.publish(report);
            // Reuse PX4's existing NAMED_VALUE_FLOAT stream to observe the
            // uORB result without maintaining a custom MAVLink dialect.
            debug_key_value_s debug{};
            debug.timestamp = now;
            std::strncpy(debug.key, "id_guard", sizeof(debug.key));
            debug.value = guard.state * 10 + guard.reason;
            debug_pub.publish(debug);
            last_report = now;
        }
        px4_usleep(50000);
    }
    running.store(false);
    return 0;
}

extern "C" __EXPORT int identity_guard_main(int argc, char *argv[]);
int identity_guard_main(int argc, char *argv[])
{
    if (argc > 1 && std::strcmp(argv[1], "start") == 0) {
        if (running.exchange(true)) { return 0; }
        stop_requested.store(false);
        const int task = px4_task_spawn_cmd("identity_guard", SCHED_DEFAULT, SCHED_PRIORITY_DEFAULT,
                                         3000, guard_run, nullptr);
        if (task < 0) { running.store(false); return -1; }
        return 0;
    }
    if (argc > 1 && std::strcmp(argv[1], "stop") == 0) {
        stop_requested.store(true);
        return 0;
    }
    PX4_INFO("running=%d; listener identity_status shows the uORB state", static_cast<int>(running.load()));
    return 0;
}

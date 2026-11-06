#include "guard.hpp"
#include <cassert>
#include <limits>

int main()
{
    Guard guard;
    guard.pulse(100);
    guard.tick(2000100);
    assert(guard.state == 1);
    guard.tick(2000101);
    assert(guard.state == 2 && guard.reason == 1);
    guard.pulse(2000200);
    assert(guard.state == 2); // liveness cannot clear a failed authentication
    assert(!guard.reset(true));
    assert(guard.state == 2);
    assert(guard.reset(false));
    guard.pulse(3000000);
    guard.reject(3);
    assert(guard.state == 2 && guard.reason == 3);
    guard.reject(4);
    assert(guard.reason == 3); // preserve the first cause
    assert(guard.landing_required(true));
    assert(!guard.landing_required(false));
    guard.reset(false);
    guard.signal(4000000, false, std::numeric_limits<float>::quiet_NaN(), 0.f);
    guard.signal(4000000, false, 1.5f, 0.f);
    assert(guard.state == 0);
    guard.signal(4000000, false, 1.f, 0.f);
    assert(guard.state == 1);
    guard.signal(4000100, true, 2.f, std::numeric_limits<float>::infinity());
    assert(guard.state == 1);
    guard.signal(4000100, true, 2.f, 2.f);
    assert(guard.state == 2 && guard.reason == 2);
    guard.signal(4000200, true, 3.f, 0.f);
    assert(guard.state == 2);
    guard.signal(4000200, false, 3.f, 0.f);
    assert(guard.state == 0);
}

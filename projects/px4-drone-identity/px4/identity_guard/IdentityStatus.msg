uint64 timestamp
uint64 last_authenticated_heartbeat
uint8 state  # 0 idle, 1 authenticated, 2 latched failsafe
uint8 reason # 1 timeout, 2 identity, 3 signature/replay, 4 role/policy, 5 disconnect
bool armed

px4_add_module(
    MODULE modules__identity_guard
    MAIN identity_guard
    SRCS identity_guard.cpp
    DEPENDS px4_work_queue
)

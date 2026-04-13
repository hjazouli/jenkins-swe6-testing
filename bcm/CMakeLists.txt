cmake_minimum_required(VERSION 3.10)
project(BCM_Project_Automotive)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra -Wpedantic")

# Include directories
include_directories(include)

# Source files
set(BCM_SOURCES
    src/bcm_core.c
    src/bcm_abs.c
    src/bcm_regen.c
    src/bcm_ebd.c
    src/bcm_hsa.c
    src/bcm_safety.c
    src/bcm_diag.c
    src/bcm_hwmon.c
)

# Main Library for the ASW Logic
add_library(bcm_asw STATIC ${BCM_SOURCES})

# Future: Add unit tests linking to bcm_asw
# add_executable(test_suite test/test_main.c)
# target_link_libraries(test_suite bcm_asw unity)

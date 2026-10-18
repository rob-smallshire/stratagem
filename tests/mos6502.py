"""Run 6502 subroutines in py65, for fast tests of routines that need no OS."""

from __future__ import annotations

from py65.devices.mpu6502 import MPU

RETURN_SENTINEL = 0xFFF0


class Machine6502:
    def __init__(self) -> None:
        self.mpu = MPU()

    def load(self, address: int, data: bytes) -> None:
        self.mpu.memory[address:address + len(data)] = list(data)

    def call(self, address: int, a: int = 0, x: int = 0, y: int = 0, max_steps: int = 100_000) -> "Machine6502":
        """JSR to address with the given registers and run until it returns."""
        mpu = self.mpu
        mpu.a, mpu.x, mpu.y = a, x, y
        mpu.sp = 0xFF
        ret = RETURN_SENTINEL - 1    # RTS adds one
        mpu.memory[0x1FF] = ret >> 8
        mpu.memory[0x1FE] = ret & 0xFF
        mpu.sp = 0xFD
        mpu.pc = address
        for _ in range(max_steps):
            if mpu.pc == RETURN_SENTINEL:
                return self
            mpu.step()
        raise TimeoutError(f"subroutine at &{address:04X} did not return in {max_steps} steps")

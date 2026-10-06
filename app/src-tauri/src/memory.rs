//! The idle-memory probe.
//!
//! Sotto's product promise is that it "consumes almost nothing when idle".
//! M0's job here is not to make that true, it is to produce the **baseline
//! number** that every later milestone is compared against. An idle claim that
//! was never sampled is worth nothing, so this samples on demand and says
//! which API produced it.

use serde::Serialize;

/// One sample of this process's memory use.
#[derive(Debug, Clone, Copy, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MemorySample {
    /// Resident working set, in bytes. This is the number the idle contract
    /// is written against.
    pub working_set_bytes: u64,
    /// Bytes committed to the page file / private commit.
    pub commit_bytes: u64,
    /// Private bytes (private commit charge).
    pub private_bytes: u64,
    pub pid: u32,
    /// Which API produced these numbers. A sample without a source is an
    /// assertion, not a measurement.
    pub source: &'static str,
    pub available: bool,
}

impl MemorySample {
    /// Working set in KiB, for humans reading a log.
    pub fn working_set_kib(&self) -> u64 {
        self.working_set_bytes / 1024
    }
}

#[cfg(target_os = "windows")]
mod imp {
    use super::MemorySample;

    /// `PROCESS_MEMORY_COUNTERS_EX`. The `EX` suffix is what adds
    /// `private_usage`; the leading fields are laid out identically to
    /// `PROCESS_MEMORY_COUNTERS`, so `cb` of `size_of::<Self>()` is what makes
    /// the API fill the last field too.
    #[repr(C)]
    #[derive(Clone, Copy)]
    struct ProcessMemoryCountersEx {
        cb: u32,
        page_fault_count: u32,
        peak_working_set_size: usize,
        working_set_size: usize,
        quota_peak_paged_pool_usage: usize,
        quota_paged_pool_usage: usize,
        quota_peak_non_paged_pool_usage: usize,
        quota_non_paged_pool_usage: usize,
        pagefile_usage: usize,
        peak_pagefile_usage: usize,
        private_usage: usize,
    }

    // `GetCurrentProcess` is a kernel32 export; `GetProcessMemoryInfo` is a
    // psapi export. kernel32 only forwards it under the `K32` name, so linking
    // the unprefixed symbol against kernel32 fails at link time.
    #[link(name = "kernel32")]
    extern "system" {
        fn GetCurrentProcess() -> isize;
    }

    #[link(name = "psapi")]
    extern "system" {
        fn GetProcessMemoryInfo(
            process: isize,
            counters: *mut ProcessMemoryCountersEx,
            cb: u32,
        ) -> i32;
    }

    pub fn sample() -> MemorySample {
        let mut counters = ProcessMemoryCountersEx {
            cb: std::mem::size_of::<ProcessMemoryCountersEx>() as u32,
            page_fault_count: 0,
            peak_working_set_size: 0,
            working_set_size: 0,
            quota_peak_paged_pool_usage: 0,
            quota_paged_pool_usage: 0,
            quota_peak_non_paged_pool_usage: 0,
            quota_non_paged_pool_usage: 0,
            pagefile_usage: 0,
            peak_pagefile_usage: 0,
            private_usage: 0,
        };

        // SAFETY: `counters` is a live, correctly-sized, zeroed struct and the
        // handle is the pseudo-handle for the current process, which the API
        // documents as always valid. No pointer outlives this call.
        let ok = unsafe {
            GetProcessMemoryInfo(
                GetCurrentProcess(),
                &mut counters,
                std::mem::size_of::<ProcessMemoryCountersEx>() as u32,
            )
        } != 0;

        MemorySample {
            working_set_bytes: counters.working_set_size as u64,
            commit_bytes: counters.pagefile_usage as u64,
            private_bytes: counters.private_usage as u64,
            pid: std::process::id(),
            source: if ok {
                "GetProcessMemoryInfo"
            } else {
                "GetProcessMemoryInfo:returned-zero"
            },
            available: ok,
        }
    }
}

#[cfg(not(target_os = "windows"))]
mod imp {
    use super::MemorySample;

    /// The probe is honest about not running rather than reporting a zero that
    /// would read as "free".
    pub fn sample() -> MemorySample {
        MemorySample {
            working_set_bytes: 0,
            commit_bytes: 0,
            private_bytes: 0,
            pid: std::process::id(),
            source: "unsupported-platform",
            available: false,
        }
    }
}

/// Sample this process's memory use right now.
pub fn sample() -> MemorySample {
    imp::sample()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The probe must never claim to be available when it has no number.
    #[test]
    fn a_sample_is_either_real_or_marked_unavailable() {
        let s = sample();
        if s.available {
            assert!(
                s.working_set_bytes > 0,
                "available sample with a zero working set is a lie: {:?}",
                s
            );
            assert_eq!(s.pid, std::process::id());
        } else {
            assert_eq!(s.working_set_bytes, 0);
        }
    }

    #[test]
    fn working_set_fits_in_kib() {
        let s = sample();
        assert_eq!(s.working_set_kib(), s.working_set_bytes / 1024);
    }
}
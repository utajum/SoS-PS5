#pragma once

#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <functional>
#include <mutex>
#include <thread>

namespace AgcDriver {

class DrawBackend {
public:
    using Task = std::function<void()>;

    using StartHook = std::function<void()>;

    explicit DrawBackend(StartHook onStart) : onStart(std::move(onStart)), thread([this] { run(); }) {}

    DrawBackend(const DrawBackend&) = delete;
    DrawBackend& operator=(const DrawBackend&) = delete;

    ~DrawBackend() {
        Drain();
        {
            std::lock_guard lock(mutex);
            stopping = true;
        }
        wake.notify_all();
        if (thread.joinable()) thread.join();
    }

    void Submit(Task task) {
        std::unique_lock lock(mutex);
        if (pending.size() >= Capacity) space.wait(lock, [&] { return pending.size() < Capacity; });
        pending.push_back(std::move(task));
        queued.fetch_add(1, std::memory_order_release);
        const bool sleeping = asleep;
        lock.unlock();
        if (sleeping) wake.notify_one();
    }

    void Drain() {
        if (Idle()) return;
        std::unique_lock lock(mutex);
        idle.wait(lock, [&] { return pending.empty() && !busy.load(std::memory_order_relaxed); });
    }

    bool Idle() const {
        return queued.load(std::memory_order_acquire) == 0 && !busy.load(std::memory_order_acquire);
    }

    std::thread::id ThreadId() const { return thread.get_id(); }

    static constexpr std::size_t Capacity = 48;

private:
    void run() {
        if (onStart) onStart();
        for (;;) {
            Task task;
            {
                std::unique_lock lock(mutex);
                while (pending.empty()) {
                    if (stopping) return;

                    lock.unlock();
#ifdef _WIN32
                    for (int spin = 0; spin < 4000 && queued.load(std::memory_order_acquire) == 0; ++spin) std::this_thread::yield();
#else
                    // sched_yield is a syscall on Linux; spin briefly on pause before sleeping
                    for (int spin = 0; spin < 1000 && queued.load(std::memory_order_acquire) == 0; ++spin) __builtin_ia32_pause();
#endif
                    lock.lock();
                    if (!pending.empty() || stopping) continue;
                    asleep = true;
                    wake.wait(lock, [&] { return stopping || !pending.empty(); });
                    asleep = false;
                }
                task = std::move(pending.front());
                pending.pop_front();

                busy.store(true, std::memory_order_release);
                queued.fetch_sub(1, std::memory_order_release);
                space.notify_one();
            }
            try {
                task();
            } catch (...) {
            }
            task = nullptr;
            {
                std::lock_guard lock(mutex);
                busy.store(false, std::memory_order_release);
                if (pending.empty()) idle.notify_all();
            }
        }
    }

    StartHook onStart;
    std::mutex mutex;
    std::condition_variable wake, idle, space;
    std::deque<Task> pending;
    std::atomic<std::size_t> queued{0};
    std::atomic<bool> busy{false};
    bool stopping = false;
    bool asleep = false;
    std::thread thread;
};

}

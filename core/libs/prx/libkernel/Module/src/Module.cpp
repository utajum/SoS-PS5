#include <cstdint>
#include <cstddef>
#include <cstring>
#include <stdexcept>
#include <string>
#include "SceTypes.hpp"
#include "prx/libc/include/General.hpp"
#include "prx/libkernel/DirectMemory/DirectMemory.hpp"
#include "prx/libkernel/KernelErrors.hpp"
#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#else
#include <fstream>
#include <link.h>
#include <mutex>
#include <string_view>
#include <vector>

namespace {
// File-backed mappings do not move once loaded; the unwinder asks once per frame per throw.
struct CachedUnwind { std::uint64_t start, end; ModuleInfoForUnwind info; };
std::mutex unwindCacheMutex;
std::vector<CachedUnwind> unwindCache;

// The PS5 unwinder finds FDEs through this query; relinked images keep the title's PT_GNU_EH_FRAME.
void FillEhFrame(std::uint64_t addr, ModuleInfoForUnwind* info) {
  struct Search { std::uint64_t addr; ModuleInfoForUnwind* info; } search{addr, info};
  dl_iterate_phdr([](dl_phdr_info* image, std::size_t, void* data) {
    auto& s = *static_cast<Search*>(data);
    const ElfW(Phdr)* frames = nullptr;
    bool contains = false;
    for (std::uint16_t i = 0; i < image->dlpi_phnum; ++i) {
      const auto& h = image->dlpi_phdr[i];
      const std::uint64_t start = image->dlpi_addr + h.p_vaddr;
      if (h.p_type == PT_LOAD && s.addr >= start && s.addr - start < h.p_memsz) contains = true;
      if (h.p_type == PT_GNU_EH_FRAME) frames = &h;
    }
    if (!contains) return 0;
    const std::string_view name = image->dlpi_name ? image->dlpi_name : "";
    if (!frames || !(name.empty() || name.ends_with(".guest.prx"))) return 1;
    const std::uint64_t hdr = image->dlpi_addr + frames->p_vaddr;
    const auto* b = reinterpret_cast<const std::uint8_t*>(hdr);
    if (b[0] != 1 || b[1] != 0x1b) return 1;  // version 1, eh_frame_ptr pcrel|sdata4
    std::int32_t rel;
    std::memcpy(&rel, b + 4, sizeof rel);
    const std::uint64_t eh = hdr + 4 + static_cast<std::int64_t>(rel);
    std::uint64_t end = 0;
    for (std::uint16_t i = 0; i < image->dlpi_phnum; ++i) {
      const auto& h = image->dlpi_phdr[i];
      const std::uint64_t start = image->dlpi_addr + h.p_vaddr;
      if (h.p_type == PT_LOAD && eh >= start && eh - start < h.p_filesz) end = start + h.p_filesz;
    }
    std::uint64_t pos = eh;
    for (std::uint32_t len; pos + 4 <= end; pos += 4 + len) {
      std::memcpy(&len, reinterpret_cast<const void*>(pos), sizeof len);
      if (len == 0 || len == 0xffffffffu || len > end - pos - 4) break;
    }
    s.info->eh_frame_hdr_addr = hdr;
    s.info->eh_frame_addr = eh;
    s.info->eh_frame_size = pos - eh;
    return 1;
  }, &search);
}
}
#endif

extern "C" {
void* APS5_VABI dlopen_nid_postfix(const char* path, int flags);
void* APS5_VABI dlsym_nid_postfix(void* handle, const char* name);
int APS5_VABI dlclose_nid_postfix(void* handle);
}

namespace {
constexpr int kRtldNow = 2;
}

extern "C" {

int APS5_VABI sceKernelDlsym(KernelModule handle, const char* symbol, void** addr) {
 if (!symbol || !addr) return SCE_KERNEL_ERROR_EFAULT;
 void* found = dlsym_nid_postfix(reinterpret_cast<void*>(static_cast<intptr_t>(handle)), symbol);
 if (!found) return SCE_KERNEL_ERROR_ESRCH;
 *addr = found;
 return 0;
}

int APS5_VABI sceKernelGetModuleInfoForUnwind(uint64_t addr, int flags, ModuleInfoForUnwind* info) {
  (void)flags;
  if (!info) return SCE_KERNEL_ERROR_EFAULT;
#ifdef _WIN32
  MEMORY_BASIC_INFORMATION mbi{};
  if (!VirtualQuery(reinterpret_cast<LPCVOID>(addr), &mbi, sizeof(mbi))) return SCE_KERNEL_ERROR_ESRCH;
  info->st_size = sizeof(ModuleInfoForUnwind);
  info->eh_frame_hdr_addr = 0;
  info->eh_frame_addr = 0;
  info->eh_frame_size = 0;
  info->seg0_addr = reinterpret_cast<std::uint64_t>(mbi.BaseAddress);
  info->seg0_size = mbi.RegionSize;
  char path[4096] = {};
  DWORD len = GetMappedFileNameA(GetCurrentProcess(), mbi.BaseAddress, path, sizeof(path) - 1);
  path[len] = '\0';
  std::strncpy(info->name, path, sizeof(info->name) - 1);
  info->name[sizeof(info->name) - 1] = '\0';
  return 0;
#else
  {
    std::lock_guard lock(unwindCacheMutex);
    for (const auto& cached : unwindCache) {
      if (addr >= cached.start && addr < cached.end) { *info = cached.info; return 0; }
    }
  }
  std::ifstream maps("/proc/self/maps");
  if (!maps) throw std::runtime_error("sceKernelGetModuleInfoForUnwind: failed to open /proc/self/maps");
  std::string line;
  while (std::getline(maps, line)) {
    std::uint64_t start = 0;
    std::uint64_t end = 0;
    char perms[8] = {};
    std::uint64_t offset = 0;
    unsigned int devMajor = 0;
    unsigned int devMinor = 0;
    std::uint64_t inode = 0;
    char path[4096] = {};
    int parsed = std::sscanf(line.c_str(), "%llx-%llx %7s %llx %x:%x %llu %4095s",
      (unsigned long long*)&start, (unsigned long long*)&end, perms,
      (unsigned long long*)&offset, &devMajor, &devMinor, (unsigned long long*)&inode, path);
    if (parsed < 7 || addr < start || addr >= end) continue;
    info->st_size = sizeof(ModuleInfoForUnwind);
    std::strncpy(info->name, parsed >= 8 ? path : "", sizeof(info->name) - 1);
    info->name[sizeof(info->name) - 1] = '\0';
    info->eh_frame_hdr_addr = 0;
    info->eh_frame_addr = 0;
    info->eh_frame_size = 0;
    info->seg0_addr = start;
    info->seg0_size = end - start;
    FillEhFrame(addr, info);
    if (info->name[0] != '\0') {
      std::lock_guard lock(unwindCacheMutex);
      unwindCache.push_back({start, end, *info});
    }
    return 0;
  }
  return SCE_KERNEL_ERROR_ESRCH;
#endif
}

int APS5_VABI sceKernelGetModuleInfoFromAddr(uint64_t addr, int n, ModuleInfo* r) {
 (void)addr;
 (void)n;
 (void)r;
 NotImplemented_nid_no_patch(__func__);
 return 0;
}

namespace {

struct PendingModuleArgs {
    std::size_t args = 0;
    const void* argp = nullptr;
};
thread_local PendingModuleArgs pendingModuleArgs;
thread_local int pendingModuleInitResult = 0;

}

extern "C" {

const void* __aps5_get_pending_module_args_nid_no_patch() {
    return &pendingModuleArgs;
}

void __aps5_set_module_init_result_nid_no_patch(int result) {
    pendingModuleInitResult = result;
}

}

KernelModule APS5_VABI sceKernelLoadStartModule(const char* module_file_name, size_t args, const void* argp, uint32_t flags, const KernelLoadModuleOpt* opt, int* res) {
 (void)flags;
 (void)opt;
 if (res) *res = 0;
 if (!module_file_name) return static_cast<KernelModule>(SCE_KERNEL_ERROR_EFAULT);
 pendingModuleArgs = {args, argp};
 pendingModuleInitResult = 0;
 void* handle = dlopen_nid_postfix(module_file_name, kRtldNow);
 const int started = pendingModuleInitResult;
 pendingModuleArgs = {};
 pendingModuleInitResult = 0;
 if (res) *res = started;
 if (!handle) return static_cast<KernelModule>(SCE_KERNEL_ERROR_ENOENT);
 return static_cast<KernelModule>(reinterpret_cast<intptr_t>(handle));
}

int APS5_VABI sceKernelStopUnloadModule(KernelModule handle, size_t args, const void* argp, uint32_t flags, const KernelUnloadModuleOpt* opt, int* res) {
 (void)args;
 (void)argp;
 (void)flags;
 (void)opt;
 if (res) *res = 0;
 return dlclose_nid_postfix(reinterpret_cast<void*>(static_cast<intptr_t>(handle))) == 0 ? 0 : SCE_KERNEL_ERROR_ESRCH;
}

}

extern "C" {

int APS5_VABI __elf_phdr_match_addr_nid_postfix(ModuleInfo* module, std::uint64_t address) {
    (void)module;
    (void)address;
    NotImplemented_nid_no_patch(__func__);
    return 0;
}

std::int32_t APS5_VABI sceKernelInternalMemoryGetModuleSegmentInfo_nid_postfix(void* result) {
    (void)result;
    NotImplemented_nid_no_patch(__func__);
    return 0;
}

}

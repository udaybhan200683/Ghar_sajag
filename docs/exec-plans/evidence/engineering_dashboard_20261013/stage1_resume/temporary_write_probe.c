/* INVESTIGATE_ONLY: libc observation of existing host fixtures, no redirection.
 * Build as a preload library for a diagnostic run. Not a product dependency.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdio.h>
#include <sys/syscall.h>
#include <unistd.h>

static void failure(const char *operation, int error) {
    char message[160];
    int count = snprintf(message, sizeof(message),
                         "GS124_TEMP_PROBE %s errno=%d\n", operation, error);
    if (count > 0) (void)syscall(SYS_write, STDERR_FILENO, message, (size_t)count);
}

ssize_t write(int fd, const void *data, size_t count) {
    ssize_t (*original)(int, const void *, size_t) = dlsym(RTLD_NEXT, "write");
    ssize_t result = original(fd, data, count);
    int error = errno;
    if (result < 0) failure("write", error);
    errno = error;
    return result;
}

size_t fwrite(const void *data, size_t size, size_t count, FILE *file) {
    size_t (*original)(const void *, size_t, size_t, FILE *) = dlsym(RTLD_NEXT, "fwrite");
    size_t result = original(data, size, count, file);
    int error = errno;
    if (result < count) failure("fwrite", error);
    errno = error;
    return result;
}

int fclose(FILE *file) {
    int (*original)(FILE *) = dlsym(RTLD_NEXT, "fclose");
    int result = original(file);
    int error = errno;
    if (result != 0) failure("fclose", error);
    errno = error;
    return result;
}

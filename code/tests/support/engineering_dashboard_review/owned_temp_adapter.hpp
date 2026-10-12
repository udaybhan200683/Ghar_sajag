#pragma once
// Inactive review fixture environment adapter only. /tmp is full in this session.
// Compile into the existing test translation unit, never firmware or production objects.
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

inline char* gs_review_owned_mkdtemp(char* original) {
    const char* root = std::getenv("TMPDIR");
    if (root == nullptr || std::strcmp(original, "/tmp/gs130-board-XXXXXX") != 0)
        return ::mkdtemp(original);
    thread_local std::vector<char> buffer;
    const std::string path = std::string(root) + "/gs130-board-XXXXXX";
    buffer.assign(path.begin(), path.end());
    buffer.push_back('\0');
    return ::mkdtemp(buffer.data());
}
#define mkdtemp gs_review_owned_mkdtemp

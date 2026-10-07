#pragma once
namespace gs::node::target {
// HIL qualification / factory gate only. Memory fixtures; no persisted writes.
bool qualify_zero_length_aead();
}

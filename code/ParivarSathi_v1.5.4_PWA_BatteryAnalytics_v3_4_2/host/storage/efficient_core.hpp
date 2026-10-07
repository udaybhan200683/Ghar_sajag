#pragma once

// Portable EXPERIMENTAL primitives. Not linked into any firmware target.
// CRC frames below detect accidental corruption; they are NOT authenticated
// storage and must never be used to justify an application ACK.
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace gs::host::storage {

inline void put_be(std::uint8_t* out, std::uint64_t value, unsigned bytes) {
    for (unsigned i = 0; i < bytes; ++i)
        out[i] = static_cast<std::uint8_t>(value >> (8 * (bytes - i - 1)));
}
inline std::uint64_t get_be(const std::uint8_t* in, unsigned bytes) {
    std::uint64_t value = 0;
    for (unsigned i = 0; i < bytes; ++i) value = (value << 8) | in[i];
    return value;
}
constexpr std::array<std::uint32_t,256> crc_table() {
    std::array<std::uint32_t,256> table{};
    for (std::size_t i=0;i<table.size();++i) {
        auto crc=static_cast<std::uint32_t>(i);
        for (unsigned bit=0;bit<8;++bit)
            crc=(crc>>1)^(0xedb88320U & (0U-(crc&1U)));
        table[i]=crc;
    }
    return table;
}
// 1 KiB read-only table trades flash for substantially lower encode CPU.
inline constexpr auto crc_lookup=crc_table();
inline std::uint32_t crc32(const std::uint8_t* data, std::size_t size) {
    std::uint32_t crc = 0xffffffffU;
    for (std::size_t i = 0; i < size; ++i) {
        crc=(crc>>8)^crc_lookup[(crc^data[i])&255U];
    }
    return ~crc;
}

// Enrollment mapping, not a truncated physical-device fingerprint. Mapping
// authenticity/lifetime is a future owner's obligation. No key counter wraps.
struct Key {
    std::uint8_t node{0};
    std::uint32_t enrollment{0};
    std::uint64_t session{0};
    std::uint64_t sequence{0};
    bool valid() const { return node < 6 && enrollment && session && sequence; }
};
using KeyBytes = std::array<std::uint8_t, 21>;
inline KeyBytes key_bytes(const Key& key) {
    KeyBytes out{};
    out[0] = key.node;
    put_be(out.data() + 1, key.enrollment, 4);
    put_be(out.data() + 5, key.session, 8);
    put_be(out.data() + 13, key.sequence, 8);
    return out;
}
struct KeyHash {
    std::uint32_t operator()(const KeyBytes& key) const {
        std::uint32_t h = 2166136261U;
        for (auto byte : key) h = (h ^ byte) * 16777619U;
        return h;
    }
};

enum class Insert { Added, Present, HandleConflict, Full, Invalid };
// Bounded open addressing + dense packed exact keys and opaque 32-bit handles.
// Handles are cache references, never durable identity or admission evidence.
// Fingerprints/hash collisions cannot establish equality. Backshift deletion
// avoids tombstones and unbounded tombstone cleanup after many lifetimes.
template<std::size_t Capacity, class Hash = KeyHash>
class ExactIndex {
    static_assert(Capacity > 0 && Capacity < 32768, "bounded uint16 index");
    static constexpr std::uint16_t empty = 0xffff;
    static constexpr std::size_t buckets_for() {
        std::size_t n = 1;
        while (n < 2 * Capacity) n *= 2;
        return n;
    }
    static constexpr std::size_t buckets = buckets_for();
    static constexpr std::size_t mask = buckets - 1;
    std::array<std::array<std::uint8_t, 25>, Capacity> rows_{};
    std::array<std::uint16_t, buckets> slots_{};
    std::uint16_t free_{0};
    std::uint16_t size_{0};
    static KeyBytes row_key(const std::array<std::uint8_t,25>& row) {
        KeyBytes key{};
        for (std::size_t i = 0; i < key.size(); ++i) key[i] = row[i];
        return key;
    }
    std::size_t home(const KeyBytes& key) const { return Hash{}(key) & mask; }
    std::size_t locate(const KeyBytes& key) const {
        auto at = home(key);
        for (std::size_t n = 0; n < buckets; ++n, at = (at + 1) & mask) {
            if (slots_[at] == empty) return buckets;
            if (row_key(rows_[slots_[at]]) == key) return at;
        }
        return buckets;
    }
public:
    static constexpr std::size_t capacity = Capacity;
    static constexpr std::size_t bucket_count = buckets;
    ExactIndex() {
        slots_.fill(empty);
        for (std::size_t i = 0; i < Capacity; ++i) {
            rows_[i][0] = 0xff;
            put_be(rows_[i].data() + 21, i + 1 == Capacity ? empty : i + 1, 4);
        }
    }
    std::size_t size() const { return size_; }
    bool find(const Key& key, std::uint32_t& handle) const {
        if (!key.valid()) return false;
        const auto slot = locate(key_bytes(key));
        if (slot == buckets) return false;
        handle = static_cast<std::uint32_t>(get_be(rows_[slots_[slot]].data()+21, 4));
        return true;
    }
    Insert insert(const Key& key, std::uint32_t handle) {
        if (!key.valid()) return Insert::Invalid;
        const auto bytes = key_bytes(key);
        auto slot = home(bytes);
        for (std::size_t n = 0; n < buckets; ++n, slot = (slot + 1) & mask) {
            if (slots_[slot] == empty) break;
            const auto& row = rows_[slots_[slot]];
            if (row_key(row) == bytes)
                return get_be(row.data()+21,4) == handle ? Insert::Present : Insert::HandleConflict;
        }
        if (size_ == Capacity) return Insert::Full;
        const auto row = free_;
        free_ = static_cast<std::uint16_t>(get_be(rows_[row].data()+21,4));
        for (std::size_t i = 0; i < bytes.size(); ++i) rows_[row][i] = bytes[i];
        put_be(rows_[row].data()+21,handle,4);
        slots_[slot] = row;
        ++size_;
        return Insert::Added;
    }
    bool erase(const Key& key) {
        if (!key.valid()) return false;
        const auto initial = locate(key_bytes(key));
        if (initial == buckets) return false;
        const auto row = slots_[initial];
        auto hole = initial;
        // Move only keys whose probe interval contains the hole, including wrap.
        auto next = (hole + 1) & mask;
        for (std::size_t n = 0; n < buckets && slots_[next] != empty;
             ++n, next = (next + 1) & mask) {
            const auto start = home(row_key(rows_[slots_[next]]));
            if (((next - start) & mask) >= ((hole - start) & mask)) {
                slots_[hole] = slots_[next];
                hole = next;
            }
        }
        slots_[hole] = empty;
        rows_[row][0] = 0xff;
        put_be(rows_[row].data()+21,free_,4);
        free_ = row;
        --size_;
        return true;
    }
};
static_assert(sizeof(KeyBytes) == 21, "exact key encoding");
static_assert(sizeof(ExactIndex<416>) == 12452, "bounded index RAM");

// Lossless current Node event numeric fields. Signed timestamps/RSSI are
// serialized modulo 2^N; decoding is defined without implementation-defined
// out-of-range unsigned-to-signed casts. IDs/location use immutable dictionaries.
struct Event {
    Key key{};
    std::uint32_t assignment{0};
    std::uint8_t kind{0}, sensor{0};
    bool test{false};
    std::int64_t monotonic{0}, occurred{0}, received{0};
    std::uint32_t uncertainty{0};
    std::uint16_t battery{0};
    std::int16_t rssi{0};
    std::uint32_t additional{0};
    std::int64_t first{0}, last{0};
};
inline std::int64_t signed64(std::uint64_t value) {
    return value <= static_cast<std::uint64_t>(INT64_MAX)
        ? static_cast<std::int64_t>(value)
        : -1 - static_cast<std::int64_t>(UINT64_MAX - value);
}
inline bool valid_event(const Event& event) {
    return event.key.valid() && event.assignment && event.kind <= 9 && event.sensor <= 5 &&
        (event.kind == 9 ? event.additional && event.first >= 0 && event.last >= event.first
                         : event.additional == 0 && event.first == 0 && event.last == 0);
}
constexpr std::size_t ordinary_bytes = 68, summary_bytes = 88;
using EventBuffer = std::array<std::uint8_t, summary_bytes>;
static_assert(summary_bytes == ordinary_bytes + 20, "rare extension only");
inline bool encode_event(const Event& event, EventBuffer& out, std::size_t& size) {
    if (!valid_event(event)) return false;
    EventBuffer candidate{};
    const auto length = event.kind == 9 ? summary_bytes : ordinary_bytes;
    candidate[0] = 1; candidate[1] = event.kind; candidate[2] = event.sensor;
    candidate[3] = event.test ? 1 : 0; candidate[4] = event.key.node;
    put_be(candidate.data()+6,length,2);
    put_be(candidate.data()+8,event.key.enrollment,4);
    put_be(candidate.data()+12,event.assignment,4);
    put_be(candidate.data()+16,event.key.session,8);
    put_be(candidate.data()+24,event.key.sequence,8);
    put_be(candidate.data()+32,static_cast<std::uint64_t>(event.monotonic),8);
    put_be(candidate.data()+40,static_cast<std::uint64_t>(event.occurred),8);
    put_be(candidate.data()+48,static_cast<std::uint64_t>(event.received),8);
    put_be(candidate.data()+56,event.uncertainty,4);
    put_be(candidate.data()+60,event.battery,2);
    put_be(candidate.data()+62,static_cast<std::uint16_t>(event.rssi),2);
    if (event.kind == 9) {
        put_be(candidate.data()+64,event.additional,4);
        put_be(candidate.data()+68,static_cast<std::uint64_t>(event.first),8);
        put_be(candidate.data()+76,static_cast<std::uint64_t>(event.last),8);
    }
    put_be(candidate.data()+length-4,crc32(candidate.data(),length-4),4);
    out = candidate; size = length;
    return true;
}
inline bool decode_event(const std::uint8_t* data, std::size_t size, Event& out) {
    if (!data || (size != ordinary_bytes && size != summary_bytes) || data[0] != 1 ||
        data[3] > 1 || data[5] != 0 || get_be(data+6,2) != size ||
        (data[1] == 9) != (size == summary_bytes) ||
        get_be(data+size-4,4) != crc32(data,size-4)) return false;
    Event candidate;
    candidate.kind=data[1]; candidate.sensor=data[2]; candidate.test=data[3]!=0;
    candidate.key.node=data[4];
    candidate.key.enrollment=static_cast<std::uint32_t>(get_be(data+8,4));
    candidate.assignment=static_cast<std::uint32_t>(get_be(data+12,4));
    candidate.key.session=get_be(data+16,8); candidate.key.sequence=get_be(data+24,8);
    candidate.monotonic=signed64(get_be(data+32,8));
    candidate.occurred=signed64(get_be(data+40,8));
    candidate.received=signed64(get_be(data+48,8));
    candidate.uncertainty=static_cast<std::uint32_t>(get_be(data+56,4));
    candidate.battery=static_cast<std::uint16_t>(get_be(data+60,2));
    const auto rssi=static_cast<std::uint16_t>(get_be(data+62,2));
    candidate.rssi=rssi<=INT16_MAX ? static_cast<std::int16_t>(rssi)
        : static_cast<std::int16_t>(-1-static_cast<std::int32_t>(UINT16_MAX-rssi));
    if (size == summary_bytes) {
        candidate.additional=static_cast<std::uint32_t>(get_be(data+64,4));
        candidate.first=signed64(get_be(data+68,8)); candidate.last=signed64(get_be(data+76,8));
    }
    if (!valid_event(candidate)) return false;
    out=candidate;
    return true;
}

// Bounded parser for a buffer of CRC-framed experimental records. It neither
// decrypts nor treats parsed records as committed/authenticated transactions.
class RecordCursor {
    const std::uint8_t* data_;
    std::size_t size_, at_{0};
public:
    RecordCursor(const std::uint8_t* data, std::size_t size) : data_(data),size_(size) {}
    bool next(Event& event) {
        if (!data_ || at_ > size_ || size_-at_ < 8) return false;
        const auto length=static_cast<std::size_t>(get_be(data_+at_+6,2));
        if (length > size_-at_ || !decode_event(data_+at_,length,event)) return false;
        at_+=length; return true;
    }
    std::size_t offset() const { return at_; }
    bool done() const { return at_ == size_; }
};

// Generic exact bounded sufficient-statistic primitive, not a selected routine
// model or decay policy. Up to UINT32_MAX unsigned 16-bit samples, without any
// float or division on update. Reject count overflow atomically.
struct Moments {
    std::uint32_t count{0};
    std::uint64_t sum{0}, squares{0};
    bool update(std::uint16_t sample) {
        const auto square=std::uint64_t{sample}*sample;
        if (count == UINT32_MAX || sum > UINT64_MAX-sample || squares > UINT64_MAX-square)
            return false;
        ++count; sum+=sample; squares+=square;
        return true;
    }
    double mean() const { return count ? static_cast<double>(sum)/count : 0; }
    double variance() const {
        if (!count) return 0;
        const auto m=mean();
        const auto v=static_cast<double>(squares)/count-m*m;
        return v < 0 ? 0 : v;
    }
    bool valid() const {
        if (!count) return sum == 0 && squares == 0;
        const auto max_sum=std::uint64_t{count}*UINT16_MAX;
        const auto max_squares=max_sum*UINT16_MAX;
        if (sum>max_sum || squares>max_squares || squares<sum) return false;
        // Minimal square sum for integer samples of a fixed total; no overflow.
        const auto q=sum/count, r=sum%count;
        const auto minimum=q*q*count+(2*q+1)*r;
        return squares>=minimum && squares<=sum*UINT16_MAX;
    }
};
static_assert(sizeof(Moments) <= 24, "bounded RAM layout; encoded fields use 20 bytes");
constexpr std::size_t stats_bytes=28;
using StatsBuffer=std::array<std::uint8_t,stats_bytes>;
inline bool encode_stats(const Moments& stats, StatsBuffer& out) {
    if (!stats.valid()) return false;
    StatsBuffer candidate{};
    candidate[0]=1;
    put_be(candidate.data()+4,stats.count,4);
    put_be(candidate.data()+8,stats.sum,8);
    put_be(candidate.data()+16,stats.squares,8);
    put_be(candidate.data()+24,crc32(candidate.data(),24),4);
    out=candidate; return true;
}
inline bool decode_stats(const std::uint8_t* data, std::size_t size, Moments& out) {
    if (!data || size!=stats_bytes || data[0]!=1 || data[1] || data[2] || data[3] ||
        get_be(data+24,4)!=crc32(data,24)) return false;
    Moments candidate;
    candidate.count=static_cast<std::uint32_t>(get_be(data+4,4));
    candidate.sum=get_be(data+8,8); candidate.squares=get_be(data+16,8);
    if (!candidate.valid()) return false;
    out=candidate; return true;
}
} // namespace gs::host::storage

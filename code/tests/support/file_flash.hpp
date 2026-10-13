#pragma once
// Simulated byte-addressed persistence boundary, not ESP flash physics.
#include "firmware/hub/storage/durable_event_outbox.hpp"
#include <filesystem>
#include <fstream>
#include <unistd.h>
#include <stdexcept>

namespace gs::test {
struct TempFlash {
    std::filesystem::path path;
    TempFlash() {
        auto name=(std::filesystem::temp_directory_path()/"gs130-board-XXXXXX").string();
        auto p=mkdtemp(name.data());
        if(!p)throw std::runtime_error("cannot create owned simulated flash");
        path=p;
    }
    ~TempFlash(){std::error_code error;std::filesystem::remove_all(path,error);}
};
inline security::Bytes read_file(const std::filesystem::path& p){
    std::ifstream input(p,std::ios::binary);
    return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
}
inline bool write_file(const std::filesystem::path& p,const security::Bytes& bytes){
    auto temporary=p;temporary+=".tmp";
    {std::ofstream out(temporary,std::ios::binary|std::ios::trunc);
     out.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());
     out.flush();if(!out)return false;}
    std::error_code error;std::filesystem::rename(temporary,p,error);return !error;
}
struct FileBlob final:security::SecurityBlobStore{
    std::filesystem::path path;bool fail_write=false;
    explicit FileBlob(std::filesystem::path p):path(std::move(p)){}
    bool read(security::Bytes& out,bool& found)override{
        found=std::filesystem::exists(path);out=found?read_file(path):security::Bytes{};return true;
    }
    bool write(const security::Bytes& in)override{return !fail_write&&write_file(path,in);}
};
class FileSegments final:public hub::storage::SegmentStore{
    std::filesystem::path root;
    std::filesystem::path segment(std::uint16_t id)const{return root/("segment-"+std::to_string(id));}
    bool size(const std::filesystem::path& p,bool& exists,std::uint32_t& bytes){
        exists=std::filesystem::exists(p);bytes=exists?std::filesystem::file_size(p):0;return true;
    }
    bool read_at(const std::filesystem::path& p,std::uint32_t offset,std::uint8_t* out,std::size_t count,std::size_t& actual){
        auto data=read_file(p);actual=offset>=data.size()?0:std::min(count,data.size()-offset);
        if(actual){std::copy_n(data.begin()+offset,actual,out);}
        return true;
    }
    bool append_at(const std::filesystem::path& p,const std::uint8_t* bytes,std::size_t count){
        std::ofstream out(p,std::ios::binary|std::ios::app);
        out.write(reinterpret_cast<const char*>(bytes),count);out.flush();return bool(out);
    }
    bool read_marker(const char* name,security::Bytes& out,bool& found){
        found=std::filesystem::exists(root/name);out=found?read_file(root/name):security::Bytes{};return true;
    }
public:
    bool fail_publication=false;
    explicit FileSegments(std::filesystem::path p):root(std::move(p)){std::filesystem::create_directories(root);}
    std::uint64_t partition_capacity_bytes()const override{return 4U*1024U*1024U;}
    bool segment_size(std::uint16_t id,bool& found,std::uint32_t& bytes)override{return size(segment(id),found,bytes);}
    bool read(std::uint16_t id,std::uint32_t offset,std::uint8_t* out,std::size_t count,std::size_t& actual)override{return read_at(segment(id),offset,out,count,actual);}
    bool append(std::uint16_t id,const std::uint8_t* in,std::size_t count)override{return append_at(segment(id),in,count);}
    bool sync(std::uint16_t)override{return true;} // Logical barrier only; no power-cut claim.
    bool read_publication(security::Bytes& out,bool& found)override{return read_marker("head",out,found);}
    bool publish_publication(const security::Bytes& bytes)override{
        if(fail_publication){fail_publication=false;return false;}return write_file(root/"head",bytes);
    }
    bool read_lifecycle_root(security::Bytes& out,bool& found)override{return read_marker("lifecycle",out,found);}
    bool publish_lifecycle_root(const security::Bytes& bytes)override{return write_file(root/"lifecycle",bytes);}
    bool remove_segment(std::uint16_t id)override{std::error_code error;std::filesystem::remove(segment(id),error);return !error;}
    bool completion_size(bool& found,std::uint32_t& bytes)override{return size(root/"completion",found,bytes);}
    bool read_completion(std::uint32_t offset,std::uint8_t* out,std::size_t count,std::size_t& actual)override{return read_at(root/"completion",offset,out,count,actual);}
    bool append_completion(const std::uint8_t* in,std::size_t count)override{return append_at(root/"completion",in,count);}
    bool sync_completion()override{return true;}
    bool truncate_completion(std::uint32_t count)override{
        auto bytes=read_file(root/"completion");if(count>bytes.size())return false;
        bytes.resize(count);return write_file(root/"completion",bytes);
    }
    bool read_completion_publication(security::Bytes& out,bool& found)override{return read_marker("completion-head",out,found);}
    bool publish_completion_publication(const security::Bytes& bytes)override{return write_file(root/"completion-head",bytes);}
};
}

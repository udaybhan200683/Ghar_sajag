#!/usr/bin/env python3
"""Offline reset contract test using production codecs/PSA and IDF guard code.
Requires a portable TF-PSA-Crypto build from the installed IDF source; no ports.
"""
import argparse
from pathlib import Path
import os
import subprocess
import tempfile

def run(argv):subprocess.run([str(a) for a in argv],check=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--crypto-build',type=Path,required=True)
    p.add_argument('--compat-include',type=Path,required=True)
    p.add_argument('--post-records',type=Path)
    p.add_argument('--psa-source',type=Path)
    args=p.parse_args()
    root=Path(__file__).resolve().parents[2]
    idf=Path(os.environ.get('IDF_PATH','/home/udaybhan/.espressif/v6.0.3/esp-idf'))
    mbed=idf/'components/mbedtls/mbedtls/tf-psa-crypto'
    source=(idf/'components/mbedtls/port/aes/esp_aes_gcm.c').read_text()
    start=source.index('int esp_aes_gcm_update(')
    prefix=source[source.index('{',start)+1:source.index('/* Honor the documented contract',start)]
    assert 'No input supplied' in prefix and 'No output supplied' in prefix
    with tempfile.TemporaryDirectory(prefix='gs_factory_reset_test_') as temp:
        folder=Path(temp)
        guard=folder/'idf_guard.c'
        guard.write_text('#include <stddef.h>\n#include <stdint.h>\n#define ESP_LOGE(...) ((void)0)\n#define TAG "test"\n#define PSA_ERROR_INVALID_ARGUMENT (-135)\n#define AES_BLOCK_BYTES 16\nint idf_gcm_pointer_guard(const unsigned char *input,size_t input_length,unsigned char *output,size_t output_size){\nint dummy=0;void *ctx=&dummy;size_t result=0;size_t *output_length=&result;\n'+prefix+'\nreturn 0;}\n')
        obj=folder/'guard.o'
        run(['cc','-c',guard,'-o',obj])
        includes=[root,root/'shared/include',mbed/'include',mbed/'drivers/builtin/include',args.crypto_build/'include',args.compat_include]
        libraries=list(args.crypto_build.rglob('*.a'))
        assert libraries,'No portable PSA libraries found'
        wrapper=folder/'psa_guard.cpp'
        wrapper.write_text(r"""
#include <psa/crypto.h>
extern "C" int idf_gcm_pointer_guard(const unsigned char*,size_t,unsigned char*,size_t);
extern "C" psa_status_t __real_psa_aead_encrypt(mbedtls_svc_key_id_t,psa_algorithm_t,const uint8_t*,size_t,const uint8_t*,size_t,const uint8_t*,size_t,uint8_t*,size_t,size_t*);
extern "C" psa_status_t __real_psa_aead_decrypt(mbedtls_svc_key_id_t,psa_algorithm_t,const uint8_t*,size_t,const uint8_t*,size_t,const uint8_t*,size_t,uint8_t*,size_t,size_t*);
extern "C" psa_status_t __wrap_psa_aead_encrypt(mbedtls_svc_key_id_t key,psa_algorithm_t alg,const uint8_t* nonce,size_t nn,const uint8_t* aad,size_t an,const uint8_t* input,size_t in,uint8_t* output,size_t on,size_t* written){
    if(idf_gcm_pointer_guard(input,in,output,on)!=0)return PSA_ERROR_INVALID_ARGUMENT;
    return __real_psa_aead_encrypt(key,alg,nonce,nn,aad,an,input,in,output,on,written);
}
extern "C" psa_status_t __wrap_psa_aead_decrypt(mbedtls_svc_key_id_t key,psa_algorithm_t alg,const uint8_t* nonce,size_t nn,const uint8_t* aad,size_t an,const uint8_t* input,size_t in,uint8_t* output,size_t on,size_t* written){
    if(idf_gcm_pointer_guard(input,in>=16?in-16:0,output,on)!=0)return PSA_ERROR_INVALID_ARGUMENT;
    return __real_psa_aead_decrypt(key,alg,nonce,nn,aad,an,input,in,output,on,written);
}
""")
        exe=folder/'validation'
        run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror',*[f'-I{i}' for i in includes],root/'firmware/common/security/association_persistence.cpp',args.psa_source or root/'firmware/common/security/psa_commissioning_crypto.cpp',wrapper,'-Wl,--wrap=psa_aead_encrypt','-Wl,--wrap=psa_aead_decrypt',root/'tests/cpp/factory_node_reset_validation.cpp',obj,'-Wl,--start-group',*libraries,'-Wl,--end-group','-o',exe])
        run([exe,*([args.post_records] if args.post_records else [])])
if __name__=='__main__':main()

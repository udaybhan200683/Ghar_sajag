#include "zero_length_aead_qualification.hpp"
#include "firmware/common/security/psa_commissioning_crypto.hpp"
#include "tests/cpp/node_empty_aead_checks.hpp"
#include "sdkconfig.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#if !CONFIG_MBEDTLS_HARDWARE_AES
#error This target regression must exercise ESP-IDF accelerated AES
#endif
namespace gs::node::target {
namespace {
constexpr char tag[]="gs_empty_aead_target";
class NoStoredIdentity final:public security::IdentitySigner {
    bool public_key(const std::string&,security::P256PublicKey&)override{return false;}
    bool sign_hash(const std::string&,const security::Key32&,security::P256Signature&)override{return false;}
};
struct Context { SemaphoreHandle_t done;bool passed{false}; };
void test_task(void* argument) {
    auto& context=*static_cast<Context*>(argument);
    NoStoredIdentity identity;security::PsaCommissioningCrypto crypto(identity);
    const auto result=qualification::check_node_empty_aead(crypto);
    context.passed=crypto.ready()&&result.passed;
    ESP_LOGI(tag,"NODE_EMPTY_AEAD_TARGET result=%s backend=ESP_IDF_PSA_HARDWARE_AES checks=%u stage=%s minimum_free_bytes=%u",
             context.passed?"PASS":"FAIL",result.checks,result.stage,
             static_cast<unsigned>(uxTaskGetStackHighWaterMark(nullptr)));
    xSemaphoreGive(context.done);
    vTaskDelete(nullptr);
}
}
bool qualify_zero_length_aead() {
    Context context{xSemaphoreCreateBinary(),false};
    if(!context.done)return false;
    if(xTaskCreate(test_task,"empty_aead_gate",20480,&context,5,nullptr)!=pdPASS){vSemaphoreDelete(context.done);return false;}
    // Retain context until the task completes, including any exceptional delay.
    xSemaphoreTake(context.done,portMAX_DELAY);
    vSemaphoreDelete(context.done);
    return context.passed;
}
}

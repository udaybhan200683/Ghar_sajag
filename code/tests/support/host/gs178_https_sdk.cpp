// Host SDK boundary for the production HttpsBackendChannel. Uses real OpenSSL
// TLS 1.2, CA/hostname validation and client certificate proof of possession.
// Only loopback is supported. No physical SDK or DS signing claim.
#include "esp_http_client.h"
#include <arpa/inet.h>
#include <chrono>
#include <cstring>
#include <openssl/pem.h>
#include <openssl/ssl.h>
#include <stdexcept>
#include <string>
#include <sys/socket.h>
#include <unistd.h>

struct FakeHttpClient {
  std::string host, path, ca, cert, key, request, response;
  int port{0}, fd{-1}, status{0}, length{0};
  std::size_t read{0};
  SSL_CTX *context{nullptr};
  SSL *ssl{nullptr};
};

std::int64_t esp_timer_get_time() {
  return std::chrono::duration_cast<std::chrono::microseconds>(
             std::chrono::steady_clock::now().time_since_epoch())
      .count();
}

esp_http_client_handle_t
esp_http_client_init(const esp_http_client_config_t *c) {
  if (!c || !c->url || !c->cert_pem || !c->client_cert_pem ||
      !c->client_key_pem || c->ds_data || c->skip_cert_common_name_check ||
      !c->disable_auto_redirect)
    return nullptr;
  const std::string url(c->url);
  const auto split = url.find('/', 8);
  if (url.rfind("https://localhost:", 0) != 0 || split == std::string::npos)
    return nullptr;
  auto client = new FakeHttpClient;
  try {
    client->port = std::stoi(url.substr(18, split - 18));
  } catch (...) {
    delete client;
    return nullptr;
  }
  if (client->port <= 0 || client->port > 65535) {
    delete client;
    return nullptr;
  }
  client->host = "localhost";
  client->path = url.substr(split);
  client->ca = c->cert_pem;
  client->cert = c->client_cert_pem;
  client->key = c->client_key_pem;
  return client;
}
esp_err_t esp_http_client_set_header(esp_http_client_handle_t, const char *,
                                     const char *) {
  return ESP_OK;
}
esp_err_t esp_http_client_open(esp_http_client_handle_t c, int length) {
  if (!c || length < 1 || length > 2048)
    return -1;
  c->length = length;
  c->context = SSL_CTX_new(TLS_client_method());
  if (!c->context)
    return -1;
  SSL_CTX_set_min_proto_version(c->context, TLS1_2_VERSION);
  SSL_CTX_set_max_proto_version(c->context, TLS1_2_VERSION);
  SSL_CTX_set_verify(c->context, SSL_VERIFY_PEER, nullptr);
  BIO *ca = BIO_new_mem_buf(c->ca.data(), static_cast<int>(c->ca.size()));
  BIO *cb = BIO_new_mem_buf(c->cert.data(), static_cast<int>(c->cert.size()));
  BIO *kb = BIO_new_mem_buf(c->key.data(), static_cast<int>(c->key.size()));
  X509 *root = PEM_read_bio_X509(ca, nullptr, nullptr, nullptr);
  X509 *cert = PEM_read_bio_X509(cb, nullptr, nullptr, nullptr);
  EVP_PKEY *key = PEM_read_bio_PrivateKey(kb, nullptr, nullptr, nullptr);
  const bool valid =
      root && cert && key &&
      X509_STORE_add_cert(SSL_CTX_get_cert_store(c->context), root) == 1 &&
      SSL_CTX_use_certificate(c->context, cert) == 1 &&
      SSL_CTX_use_PrivateKey(c->context, key) == 1 &&
      SSL_CTX_check_private_key(c->context) == 1;
  X509_free(root);
  X509_free(cert);
  EVP_PKEY_free(key);
  BIO_free(ca);
  BIO_free(cb);
  BIO_free(kb);
  if (!valid)
    return -1;
  c->fd = socket(AF_INET, SOCK_STREAM, 0);
  if (c->fd < 0)
    return -1;
  timeval timeout{3, 0};
  setsockopt(c->fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
  setsockopt(c->fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(c->port);
  addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  if (connect(c->fd, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) != 0)
    return -1;
  c->ssl = SSL_new(c->context);
  if (!c->ssl)
    return -1;
  SSL_set_fd(c->ssl, c->fd);
  SSL_set_tlsext_host_name(c->ssl, "localhost");
  SSL_set1_host(c->ssl, "localhost");
  return SSL_connect(c->ssl) == 1 && SSL_get_verify_result(c->ssl) == X509_V_OK
             ? ESP_OK
             : -1;
}
int esp_http_client_write(esp_http_client_handle_t c, const char *data,
                          int length) {
  if (!c || length <= 0 ||
      c->request.size() + static_cast<std::size_t>(length) >
          static_cast<std::size_t>(c->length))
    return -1;
  c->request.append(data, length);
  return length;
}
std::int64_t esp_http_client_fetch_headers(esp_http_client_handle_t c) {
  if (!c || c->request.size() != static_cast<std::size_t>(c->length))
    return -1;
  auto wire = "POST " + c->path +
              " HTTP/1.1\r\nHost: localhost\r\nContent-Type: "
              "application/json\r\nConnection: close\r\nContent-Length: " +
              std::to_string(c->length) + "\r\n\r\n" + c->request;
  std::size_t sent = 0;
  while (sent < wire.size()) {
    const auto n = SSL_write(c->ssl, wire.data() + sent, wire.size() - sent);
    if (n <= 0)
      return -1;
    sent += n;
  }
  std::string received;
  char buf[1024];
  std::size_t header;
  while ((header = received.find("\r\n\r\n")) == std::string::npos) {
    const auto n = SSL_read(c->ssl, buf, sizeof(buf));
    if (n <= 0 || received.size() + n > 8192)
      return -1;
    received.append(buf, n);
  }
  const auto start = received.find(' ');
  if (start == std::string::npos)
    return -1;
  c->status = std::stoi(received.substr(start + 1, 3));
  const auto marker = received.find("Content-Length: ");
  if (marker == std::string::npos || marker > header)
    return -1;
  const auto size = std::stoul(received.substr(marker + 16));
  if (size > 1024)
    return -1;
  c->response = received.substr(header + 4);
  while (c->response.size() < size) {
    const auto n =
        SSL_read(c->ssl, buf, std::min(sizeof(buf), size - c->response.size()));
    if (n <= 0)
      return -1;
    c->response.append(buf, n);
  }
  return c->response.size() == size ? static_cast<std::int64_t>(size) : -1;
}
int esp_http_client_get_status_code(esp_http_client_handle_t c) {
  return c->status;
}
int esp_http_client_read(esp_http_client_handle_t c, char *out, int length) {
  const auto n =
      std::min(static_cast<std::size_t>(length), c->response.size() - c->read);
  std::memcpy(out, c->response.data() + c->read, n);
  c->read += n;
  return static_cast<int>(n);
}
bool esp_http_client_is_complete_data_received(esp_http_client_handle_t c) {
  return c->read == c->response.size();
}
esp_err_t esp_http_client_close(esp_http_client_handle_t c) {
  if (c) {
    if (c->ssl) {
      SSL_free(c->ssl);
      c->ssl = nullptr;
    }
    if (c->fd >= 0) {
      close(c->fd);
      c->fd = -1;
    }
  }
  return ESP_OK;
}
esp_err_t esp_http_client_cleanup(esp_http_client_handle_t c) {
  if (c) {
    esp_http_client_close(c);
    SSL_CTX_free(c->context);
    OPENSSL_cleanse(c->key.data(), c->key.size());
    delete c;
  }
  return ESP_OK;
}

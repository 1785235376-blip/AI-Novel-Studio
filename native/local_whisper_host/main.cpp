// Fixed-model Windows host. No /load, discovery, file URLs, model selection,
// shell commands, external ffmpeg or general upstream server UI is exposed.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>
#include "whisper.h"
#include "httplib.h"
#include "json.hpp"
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <memory>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

using json = nlohmann::ordered_json;
constexpr size_t MAX_PCM_BYTES = 20 * 1024 * 1024;
constexpr const char * PROTOCOL = "studio-fixed-whisper-host/1";

struct Handle {
    HANDLE value = INVALID_HANDLE_VALUE;
    explicit Handle(HANDLE handle) : value(handle) {
        if (value == INVALID_HANDLE_VALUE || value == nullptr) throw std::runtime_error("HOST_FILE_OPEN_FAILED");
    }
    ~Handle() { CloseHandle(value); }
    Handle(const Handle &) = delete;
    Handle & operator=(const Handle &) = delete;
};

std::wstring wide(const std::string & value) {
    if (value.empty() || value.size() > 8192 || value.find('\0') != std::string::npos) throw std::runtime_error("HOST_PATH_INVALID");
    const int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(), static_cast<int>(value.size()), nullptr, 0);
    if (!count) throw std::runtime_error("HOST_PATH_UTF8_INVALID");
    std::wstring result(count, 0);
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(), static_cast<int>(value.size()), &result[0], count) != count)
        throw std::runtime_error("HOST_PATH_UTF8_INVALID");
    return result;
}

bool hex64(const std::string & value) {
    return value.size() == 64 && value.find_first_not_of("0123456789abcdef") == std::string::npos;
}

void rewind_handle(HANDLE file) {
    LARGE_INTEGER zero{};
    if (!SetFilePointerEx(file, zero, nullptr, FILE_BEGIN)) throw std::runtime_error("HOST_FILE_SEEK_FAILED");
}

BY_HANDLE_FILE_INFORMATION identity(HANDLE file) {
    BY_HANDLE_FILE_INFORMATION result{};
    if (!GetFileInformationByHandle(file, &result) || (result.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)
            || (result.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) throw std::runtime_error("HOST_FILE_IDENTITY_INVALID");
    return result;
}

uint64_t file_size(const BY_HANDLE_FILE_INFORMATION & item) {
    return (uint64_t(item.nFileSizeHigh) << 32) | item.nFileSizeLow;
}

bool same(const BY_HANDLE_FILE_INFORMATION & a, const BY_HANDLE_FILE_INFORMATION & b) {
    return a.dwVolumeSerialNumber == b.dwVolumeSerialNumber && a.nFileIndexHigh == b.nFileIndexHigh
        && a.nFileIndexLow == b.nFileIndexLow && a.nFileSizeHigh == b.nFileSizeHigh && a.nFileSizeLow == b.nFileSizeLow
        && a.ftLastWriteTime.dwHighDateTime == b.ftLastWriteTime.dwHighDateTime
        && a.ftLastWriteTime.dwLowDateTime == b.ftLastWriteTime.dwLowDateTime;
}

std::string sha256(HANDLE file, uint64_t maximum) {
    const auto before = identity(file);
    if (!file_size(before) || file_size(before) > maximum) throw std::runtime_error("HOST_FILE_CAPACITY_INVALID");
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    BCRYPT_HASH_HANDLE hash = nullptr;
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0)
        throw std::runtime_error("HOST_HASH_UNAVAILABLE");
    DWORD object_size = 0, copied = 0;
    if (BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH, reinterpret_cast<PUCHAR>(&object_size),
            sizeof(object_size), &copied, 0) < 0) {
        BCryptCloseAlgorithmProvider(algorithm, 0);
        throw std::runtime_error("HOST_HASH_UNAVAILABLE");
    }
    std::vector<unsigned char> object(object_size), buffer(1024 * 1024), result(32);
    if (BCryptCreateHash(algorithm, &hash, object.data(), object_size, nullptr, 0, 0) < 0) {
        BCryptCloseAlgorithmProvider(algorithm, 0);
        throw std::runtime_error("HOST_HASH_UNAVAILABLE");
    }
    try {
        rewind_handle(file);
        uint64_t count = 0;
        for (;;) {
            DWORD size = 0;
            if (!ReadFile(file, buffer.data(), static_cast<DWORD>(buffer.size()), &size, nullptr))
                throw std::runtime_error("HOST_FILE_READ_FAILED");
            if (!size) break;
            count += size;
            if (count > maximum || BCryptHashData(hash, buffer.data(), size, 0) < 0)
                throw std::runtime_error("HOST_HASH_FAILED");
        }
        if (count != file_size(before) || !same(before, identity(file))
                || BCryptFinishHash(hash, result.data(), static_cast<ULONG>(result.size()), 0) < 0)
            throw std::runtime_error("HOST_FILE_CHANGED");
        BCryptDestroyHash(hash); hash = nullptr;
        BCryptCloseAlgorithmProvider(algorithm, 0); algorithm = nullptr;
        rewind_handle(file);
        std::ostringstream text;
        for (unsigned char byte : result) text << std::hex << std::setfill('0') << std::setw(2) << unsigned(byte);
        return text.str();
    } catch (...) {
        if (hash) BCryptDestroyHash(hash);
        if (algorithm) BCryptCloseAlgorithmProvider(algorithm, 0);
        throw;
    }
}

std::string control_line() {
    std::string result;
    for (int character; (character = std::getchar()) != EOF;) {
        if (character == '\n') return result;
        if (result.size() >= 16384 || character == '\r' || character == 0) throw std::runtime_error("HOST_CONTROL_INVALID");
        result.push_back(static_cast<char>(character));
    }
    throw std::runtime_error("HOST_CONTROL_CLOSED");
}

struct ModelReader {
    HANDLE file;
    uint64_t size;
    uint64_t offset = 0;
    bool failed = false;
    bool weight_read = false;
};

size_t model_read(void * opaque, void * output, size_t requested) {
    auto & reader = *static_cast<ModelReader *>(opaque);
    if (reader.failed) return 0;
    if (reader.offset == reader.size) {
        // Upstream attempts one final tensor header before checking EOF.
        // Clean end-of-file is not a truncated tensor or failed model load.
        std::memset(output, 0, requested);
        return 0;
    }
    if (requested > reader.size - reader.offset) { reader.failed = true; return 0; }
    if (requested >= 1024 * 1024) reader.weight_read = true;
    size_t total = 0;
    while (total < requested) {
        const DWORD chunk = static_cast<DWORD>(std::min<size_t>(requested - total, 1024 * 1024));
        DWORD count = 0;
        if (!ReadFile(reader.file, static_cast<unsigned char *>(output) + total, chunk, &count, nullptr) || count != chunk) {
            reader.failed = true; return total;
        }
        total += count; reader.offset += count;
    }
    return total;
}
bool model_eof(void * opaque) {
    const auto & reader = *static_cast<ModelReader *>(opaque);
    return reader.failed || reader.offset == reader.size;
}
void model_close(void *) {} // The immutable model lease remains held for the context lifetime.

uint16_t u16(const unsigned char * value) { return uint16_t(value[0]) | (uint16_t(value[1]) << 8); }
uint32_t u32(const unsigned char * value) { return uint32_t(value[0]) | (uint32_t(value[1]) << 8) | (uint32_t(value[2]) << 16) | (uint32_t(value[3]) << 24); }

std::vector<float> pcm(const std::string & body) {
    if (body.size() < 44 || body.size() > MAX_PCM_BYTES) throw std::runtime_error("HOST_PCM_CAPACITY_INVALID");
    const auto * bytes = reinterpret_cast<const unsigned char *>(body.data());
    if (std::memcmp(bytes, "RIFF", 4) || std::memcmp(bytes + 8, "WAVE", 4) || uint64_t(u32(bytes + 4)) + 8 != body.size())
        throw std::runtime_error("HOST_PCM_CONTAINER_INVALID");
    bool format = false;
    const unsigned char * data = nullptr;
    size_t data_size = 0, offset = 12, chunks = 0;
    while (offset + 8 <= body.size()) {
        if (++chunks > 32) throw std::runtime_error("HOST_PCM_CHUNKS_INVALID");
        const size_t size = u32(bytes + offset + 4);
        const size_t beginning = offset + 8;
        if (size > body.size() - beginning) throw std::runtime_error("HOST_PCM_CHUNK_INVALID");
        if (std::memcmp(bytes + offset, "fmt ", 4) == 0) {
            if (format || size < 16 || size > 64 || u16(bytes + beginning) != 1
                    || u16(bytes + beginning + 2) != 1 || u32(bytes + beginning + 4) != 16000
                    || u32(bytes + beginning + 8) != 32000 || u16(bytes + beginning + 12) != 2
                    || u16(bytes + beginning + 14) != 16) throw std::runtime_error("HOST_PCM_FORMAT_INVALID");
            format = true;
        } else if (std::memcmp(bytes + offset, "data", 4) == 0) {
            if (data || !size || size % 2) throw std::runtime_error("HOST_PCM_DATA_INVALID");
            data = bytes + beginning; data_size = size;
        }
        offset = beginning + size + (size % 2);
        if (offset > body.size()) throw std::runtime_error("HOST_PCM_PADDING_INVALID");
    }
    if (!format || !data || offset != body.size() || data_size / 2 > 16000 * 600)
        throw std::runtime_error("HOST_PCM_DURATION_INVALID");
    std::vector<float> result(data_size / 2);
    for (size_t i = 0; i < result.size(); ++i) result[i] = static_cast<int16_t>(u16(data + i * 2)) / 32768.0f;
    return result;
}

struct Abort {
    const httplib::Request * request;
    std::chrono::steady_clock::time_point deadline;
};
bool aborted(void * opaque) {
    const auto & context = *static_cast<Abort *>(opaque);
    return context.request->is_connection_closed() || std::chrono::steady_clock::now() >= context.deadline;
}

int wmain(int argc, wchar_t **) {
    if (argc != 1) return 2;
    try {
        const json config = json::parse(control_line());
        const std::vector<std::string> keys = {"schema", "model_path", "model_sha256", "executable_sha256", "token",
                                             "startup_nonce", "revision", "port", "threads", "use_gpu"};
        if (!config.is_object() || config.size() != keys.size()) throw std::runtime_error("HOST_CONTROL_INVALID");
        for (const auto & key : keys) if (!config.contains(key)) throw std::runtime_error("HOST_CONTROL_INVALID");
        if (config.at("schema") != PROTOCOL || !config.at("model_path").is_string()
                || !config.at("model_sha256").is_string() || !config.at("executable_sha256").is_string()
                || !config.at("token").is_string() || !config.at("startup_nonce").is_string()
                || !config.at("revision").is_number_unsigned() || !config.at("port").is_number_unsigned()
                || !config.at("threads").is_number_unsigned() || !config.at("use_gpu").is_boolean())
            throw std::runtime_error("HOST_CONTROL_INVALID");
        const auto revision = config.at("revision").get<uint64_t>();
        const int port = config.at("port").get<int>(), threads = config.at("threads").get<int>();
        const std::string token = config.at("token"), nonce = config.at("startup_nonce");
        const std::string expected_model = config.at("model_sha256"), expected_executable = config.at("executable_sha256");
        if (!hex64(token) || !hex64(nonce) || !hex64(expected_model) || !hex64(expected_executable)
                || !revision || revision > 9007199254740991ULL || port < 1024 || port > 65535 || threads < 1 || threads > 64)
            throw std::runtime_error("HOST_CONTROL_INVALID");
        wchar_t module[32768];
        const DWORD length = GetModuleFileNameW(nullptr, module, 32768);
        if (!length || length >= 32768) throw std::runtime_error("HOST_EXECUTABLE_IDENTITY_INVALID");
        Handle executable(CreateFileW(module, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                                      FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
        if (sha256(executable.value, 1024ULL * 1024 * 1024) != expected_executable)
            throw std::runtime_error("HOST_EXECUTABLE_PIN_MISMATCH");
        const auto model_path = wide(config.at("model_path").get<std::string>());
        Handle model(CreateFileW(model_path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                                 FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
        const auto before = identity(model.value);
        const auto actual_model = sha256(model.value, 8ULL * 1024 * 1024 * 1024);
        if (actual_model != expected_model) throw std::runtime_error("HOST_MODEL_PIN_MISMATCH");
        ModelReader reader{model.value, file_size(before)};
        whisper_model_loader loader{&reader, model_read, model_eof, model_close};
        auto context_parameters = whisper_context_default_params();
        context_parameters.use_gpu = config.at("use_gpu").get<bool>();
        context_parameters.flash_attn = false;
        std::unique_ptr<whisper_context, decltype(&whisper_free)> context(
            whisper_init_with_params(&loader, context_parameters), whisper_free);
        if (!context || reader.failed || !reader.weight_read || !same(before, identity(model.value))
                || sha256(model.value, 8ULL * 1024 * 1024 * 1024) != actual_model
                || std::string(whisper_version()) != "1.8.2") throw std::runtime_error("HOST_MODEL_LOAD_FAILED");
        auto server = std::make_shared<httplib::Server>();
        server->set_payload_max_length(MAX_PCM_BYTES + 65536);
        server->set_read_timeout(30);
        server->set_write_timeout(30);
        server->new_task_queue = [] { return new httplib::ThreadPool(1, 2); };
        const auto pid = GetCurrentProcessId();
        std::mutex inference;
        server->Post("/inference", [&](const httplib::Request & request, httplib::Response & response) {
            response.set_header("Cache-Control", "no-store");
            auto fail = [&](int code, const char * reason) { response.status = code; response.set_content(json{{"error", reason}}.dump(), "application/json"); };
            if (request.remote_addr != "127.0.0.1" || request.get_header_value("X-Studio-Whisper-Token") != token
                    || request.get_header_value("X-Studio-Whisper-Revision") != std::to_string(revision)
                    || request.get_header_value("X-Studio-Whisper-PID") != std::to_string(pid)) {
                fail(403, "HOST_PRIVATE_AUTHORIZATION_REQUIRED"); return;
            }
            const std::vector<std::pair<std::string, std::string>> expected = {
                {"response_format", "verbose_json"}, {"translate", "false"}, {"temperature", "0"}, {"temperature_inc", "0"},
                {"diarize", "false"}, {"tinydiarize", "false"}, {"no_timestamps", "false"},
                {"token_timestamps", "false"}, {"no_language_probabilities", "true"}};
            if (!request.has_file("file") || !request.has_file("language") || request.files.size() != expected.size() + 2) {
                fail(400, "HOST_ASR_PARAMETERS_INVALID"); return;
            }
            for (const auto & item : expected) if (!request.has_file(item.first)
                    || request.get_file_value(item.first).content != item.second || request.files.count(item.first) != 1) {
                fail(400, "HOST_ASR_PARAMETERS_INVALID"); return;
            }
            if (request.files.count("file") != 1 || request.files.count("language") != 1) {
                fail(400, "HOST_ASR_PARAMETERS_INVALID"); return;
            }
            const auto file = request.get_file_value("file");
            const auto language = request.get_file_value("language").content;
            if (file.filename != "input.wav" || file.content_type != "audio/wav" || language.size() > 3
                    || (language != "auto" && whisper_lang_id(language.c_str()) < 0)
                    || (!whisper_is_multilingual(context.get()) && language != "en")) {
                fail(400, "HOST_ASR_LANGUAGE_OR_FILE_INVALID"); return;
            }
            try {
                std::lock_guard<std::mutex> lease(inference);
                const auto samples = pcm(file.content);
                auto parameters = whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
                parameters.n_threads = threads;
                parameters.translate = false;
                parameters.no_context = true;
                parameters.print_realtime = parameters.print_progress = parameters.print_timestamps = parameters.print_special = false;
                parameters.no_timestamps = false;
                parameters.token_timestamps = false;
                parameters.temperature = parameters.temperature_inc = 0;
                parameters.language = language.c_str();
                // language="auto" already detects language and then transcribes.
                // detect_language=true is upstream's detect-only early-return mode.
                parameters.detect_language = false;
                Abort abort{&request, std::chrono::steady_clock::now() + std::chrono::seconds(120)};
                parameters.abort_callback = aborted;
                parameters.abort_callback_user_data = &abort;
                if (whisper_full(context.get(), parameters, samples.data(), static_cast<int>(samples.size())) != 0 || aborted(&abort)) {
                    fail(499, "HOST_ASR_ABORTED_OR_FAILED"); return;
                }
                const int segments = whisper_full_n_segments(context.get());
                if (segments < 1 || segments > 2000) { fail(422, "HOST_ASR_SEGMENT_CAPACITY_INVALID"); return; }
                json result{{"task", "transcribe"}, {"duration", double(samples.size()) / 16000},
                            {"language", whisper_lang_str(whisper_full_lang_id(context.get()))}, {"segments", json::array()}};
                size_t text_size = 0;
                for (int i = 0; i < segments; ++i) {
                    const std::string text = whisper_full_get_segment_text(context.get(), i);
                    text_size += text.size();
                    if (text.size() > 40000 || text_size > 400000) { fail(422, "HOST_ASR_TEXT_CAPACITY_INVALID"); return; }
                    result["segments"].push_back({{"id", i}, {"start", whisper_full_get_segment_t0(context.get(), i) * 0.01},
                        {"end", whisper_full_get_segment_t1(context.get(), i) * 0.01}, {"text", text}});
                }
                const auto serialized = result.dump();
                if (serialized.size() > 1024 * 1024) { fail(422, "HOST_ASR_RESPONSE_CAPACITY_INVALID"); return; }
                response.set_content(serialized, "application/json");
            } catch (...) { fail(422, "HOST_ASR_INVALID_PCM_OR_RESULT"); }
        });
        if (!server->bind_to_port("127.0.0.1", port)) throw std::runtime_error("HOST_LOOPBACK_BIND_FAILED");
        std::ostringstream id;
        id << std::hex << std::setfill('0') << std::setw(8) << before.dwVolumeSerialNumber
           << std::setw(8) << before.nFileIndexHigh << std::setw(8) << before.nFileIndexLow;
        std::cout << json{{"schema", PROTOCOL}, {"event", "MODEL_LOADED_AND_BOUND"}, {"startup_nonce", nonce},
            {"revision", revision}, {"pid", pid}, {"model_sha256", actual_model}, {"executable_sha256", expected_executable},
            {"port", port}, {"whisper_version", whisper_version()}, {"model_file_id", id.str()}, {"model_bytes", file_size(before)}}.dump()
            << std::endl;
        // Parent holds stdin for the process lifetime. EOF causes bounded
        // shutdown even if the backend is abruptly closed before normal stop.
        std::thread parent([server] {
            while (std::getchar() != EOF) {}
            server->stop();
        });
        const bool served = server->listen_after_bind();
        server->stop();
        // At normal operation parent closes stdin before terminating/joining.
        // If bind/listen fails, exit cannot wait indefinitely on a live parent.
        parent.detach();
        return served ? 0 : 1;
    } catch (...) {
        // Paths, control nonce and private token never enter public logs.
        std::fprintf(stderr, "STUDIO_FIXED_WHISPER_HOST_FAILED\n");
        return 1;
    }
}

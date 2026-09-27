#include <iostream>
#include <string>
#include <curl/curl.h>
#include <map>

class SynoDSMClient {
private:
    CURL* curl;
    std::string base_url;
    std::string sid;

    static size_t WriteCallback(void* contents, size_t size, size_t nmemb, std::string* output) {
        size_t totalSize = size * nmemb;
        output->append((char*)contents, totalSize);
        return totalSize;
    }

public:
    SynoDSMClient(const std::string& ip, int port = 5000) 
        : base_url("http://" + ip + ":" + std::to_string(port) + "/webapi/entry.cgi") {
        curl_global_init(CURL_GLOBAL_DEFAULT);
        curl = curl_easy_init();
    }

    ~SynoDSMClient() {
        if (curl) curl_easy_cleanup(curl);
        curl_global_cleanup();
    }

    // 登录并获取 SID
    bool login(const std::string& username, const std::string& password) {
        std::string response;
        std::string postData = "api=SYNO.API.Auth&version=6&method=login"
                               "&account=" + username + "&passwd=" + password +
                               "&session=FileStation&format=sid";

        curl_easy_setopt(curl, CURLOPT_URL, base_url.c_str());
        curl_easy_setopt(curl, CURLOPT_POST, 1L);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, postData.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);

        CURLcode res = curl_easy_perform(curl);
        if (res != CURLE_OK) return false;

        // 简单解析 JSON（实际项目中建议用 JSON 库）
        size_t pos = response.find("\"sid\":\"");
        if (pos == std::string::npos) return false;
        pos += 7;
        size_t end = response.find("\"", pos);
        sid = response.substr(pos, end - pos);
        return true;
    }

    // 列出共享文件夹
    std::string listShares() {
        std::string response;
        std::string postData = "api=SYNO.FileStation.List&version=2&method=list_share&_sid=" + sid;

        curl_easy_setopt(curl, CURLOPT_URL, base_url.c_str());
        curl_easy_setopt(curl, CURLOPT_POST, 1L);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, postData.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);

        curl_easy_perform(curl);
        return response;
    }

    // 上传文件
    bool uploadFile(const std::string& localPath, const std::string& remotePath) {
        std::string response;
        struct curl_httppost* form = nullptr;
        struct curl_httppost* last = nullptr;

        curl_formadd(&form, &last,
                     CURLFORM_COPYNAME, "api",
                     CURLFORM_COPYCONTENTS, "SYNO.FileStation.Upload");
        curl_formadd(&form, &last,
                     CURLFORM_COPYNAME, "version",
                     CURLFORM_COPYCONTENTS, "2");
        curl_formadd(&form, &last,
                     CURLFORM_COPYNAME, "method",
                     CURLFORM_COPYCONTENTS, "upload");
        curl_formadd(&form, &last,
                     CURLFORM_COPYNAME, "path",
                     CURLFORM_COPYCONTENTS, remotePath.c_str());
        curl_formadd(&form, &last,
                     CURLFORM_COPYNAME, "create_parents",
                     CURLFORM_COPYCONTENTS, "true");
        curl_formadd(&form, &last,
                     CURLFORM_COPYNAME, "_sid",
                     CURLFORM_COPYCONTENTS, sid.c_str());
        curl_formadd(&form, &last,
                     CURLFORM_COPYNAME, "file",
                     CURLFORM_FILE, localPath.c_str());

        std::string url = base_url + "?_sid=" + sid;
        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_HTTPPOST, form);
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);

        CURLcode res = curl_easy_perform(curl);
        curl_formfree(form);
        return res == CURLE_OK;
    }
};

// 使用示例
int main() {
    SynoDSMClient client("192.168.1.100", 5000);
    
    if (client.login("admin", "your_password")) {
        std::cout << "登录成功！" << std::endl;
        std::cout << "共享文件夹列表: " << client.listShares() << std::endl;
        client.uploadFile("/path/to/local/file.pdf", "/home/upload");
    } else {
        std::cout << "登录失败" << std::endl;
    }
    
    return 0;
}
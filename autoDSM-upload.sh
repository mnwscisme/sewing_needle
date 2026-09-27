SHARING_URL="$1"
SHARING_FILEPATH="$2"
PARAMETER3="$3"
PARAMETER4="$4"

usage()
{
    script_name=$(basename "$0")
    error_message="$1"

    echo "Author:  Hacksign"
    echo "Website: https://www.debugwar.com"
    echo "GitHub:  https://github.com/Hacksign/Articles/tree/main/Other/Automate-File-Downloads-and-Uploads-with-Synology-DSM"
    echo "License: GPLv2"
    echo "Description:"
    echo "  This script helps you download/upload file(s) from/to Synology DSM."
    echo "  NOTE: This script checks the second argument which is a filepath:"
    echo "   * If the file doesn't exist, download file in sharing content."
    echo "   * If the file exists, upload file indicated by parameter 2."
    echo "Usage:"
    echo "  download: ${script_name} [sharing url] [filepath] [password]"
    echo "    upload: ${script_name} [sharing url] [filepath] [folder name] [password]"
    echo "Example:"
    echo "  download:"
    echo "    ${script_name} https://example.com/sharing/ab0cd1EFg /path/to/file.NO.exists"
    echo "    ${script_name} https://example.com/sharing/ab0cd1EFg /path/to/file.NO.exists pwd123"
    echo "  upload:"
    echo "    ${script_name} https://example.com/sharing/ab0cd1EFg /path/to/file.exists FolderName"
    echo "    ${script_name} https://example.com/sharing/ab0cd1EFg /path/to/file.exists FolderName pwd123"

    if [[ "${error_message}x" != "x" ]]; then
        echo ""
        echo "[!] ${error_message}"
    fi
}

get_sharing_sid()
{
    sharing_host="$1"
    sharing_id="$2"
    sharing_pwd="$3"

    # request sharing_sid parameter we need next step
    response=$(curl -kvL \
        "${sharing_host}/sharing/webapi/entry.cgi/SYNO.Core.Sharing.Login" \
        --data-raw "api=SYNO.Core.Sharing.Login&method=login&version=1&sharing_id=%22${sharing_id}%22&password=%22${sharing_pwd}%22" 2>/dev/null)
    sharing_sid=$(echo ${response} | sed -n 's/.*"sharing_sid":"\(.*\)"\s*}.*/\1/p')
    if [ -z "${sharing_sid}" ]; then
        return 255
    fi

    echo ${sharing_sid}
    return 0
}

upload_to_dsm()
{
    sharing_url="$1"
    upload_filepath="$2"
    sharing_folder="$3"
    sharing_pwd="$4"
    filename=$(basename ${upload_filepath} 2>/dev/null | tr -d '\n')
    filesize=$(wc -c < "${upload_filepath}" 2>/dev/null | tr -d '\n')

    # split sharing_url by /, we need schema, host, port, share id
    old_ifs="$IFS"
    IFS='/'
    set -- $sharing_url
    sharing_host="$1//$3"
    sharing_id="$5"
    IFS="$old_ifs"

    # request sharing_sid parameter we need next step
    sharing_sid=$(get_sharing_sid "${sharing_host}" "${sharing_id}" "${sharing_pwd}")
    if [ $? -eq 0 ]; then
        #check write permission
        response=$(curl -kvL \
            "${sharing_host}/sharing/webapi/entry.cgi" \
            -H "X-SYNO-SHARING: ${sharing_id}" \
            -H "Cookie: sharing_sid=${sharing_sid}" \
            --data-raw "api=SYNO.FileStation.CheckPermission&method=write&version=3&filename=%22${filename}%22&size=${filesize}&overwrite=true&sharing_id=%22${sharing_id}%22&uploader_name=%22${sharing_folder}%22" 2>/dev/null)
        has_write_permission=$(echo ${response} | grep '"success":true')
        if [ ! -z "${has_write_permission}" ]; then
            # upload file with curl
            response=$(curl -kvL \
                "${sharing_host}/webapi/entry.cgi?api=SYNO.FileStation.Upload&method=upload&version=2&_sharing_id=${sharing_id}" \
                -H "Cookie: sharing_sid=${sharing_sid}" \
                -F "overwrite=true" \
                -F "mtime=$(date +%s)000" \
                -F "sharing_id=${sharing_id}" \
                -F "uploader_name=${sharing_folder}" \
                -F "files=@${upload_filepath}" 2>/dev/null)
            upload_successed=$(echo ${response} | grep '"success":true')
            if [ ! -z "${upload_successed}" ]; then
                return 0
            fi
        fi
    fi
    return 255
}



# check input parameter
if [[ $# == 0 ]]; then
    usage
    exit
elif [[ "${SHARING_URL}x" == "x" ]]; then
    usage "missing sharing url"
    exit
elif [[ "${SHARING_FILEPATH}x" == "x" ]]; then
    usage "missing sharing path"
    exit
fi

if [[ -e "${SHARING_FILEPATH}" ]]; then
    # when it is upload mode, parameter 3 is folder, parameter 4 is password
    upload_to_dsm "${SHARING_URL}" "${SHARING_FILEPATH}" "${PARAMETER3}" "${PARAMETER4}"
    if [[ $? == 0 ]]; then
        echo "[*] upload success."
    else
        echo "[!] upload failed."
    fi

fiy


# 获取DSM的SID
curl "http://10.10.150.14:5000/webapi/auth.cgi" -d "api=SYNO.API.Auth" -d "version=6" -d "method=login" -d "account=nbzyb-shijue" -d "passwd=Sj123456.*"  -d "session=FileStation" -d "format=sid"


# 上传文件到DSM
curl -X POST "http://10.10.150.14:5000/webapi/entry.cgi?_sid=oy3YUv2xWEHzE18A0NRN005500" -F "api=SYNO.FileStation.Upload" -F "version=2" -F "method=upload" -F "path=/shijuebackup/image" -F "create_parents=true" -F "file=@e:/SaveImage/DPJ00008/camera00/20260713/2.jpg"

# 获取DSM的文件列表
curl "http://10.10.150.14:5000/webapi/entry.cgi?api=SYNO.FileStation.List&version=2&method=list&folder_path=/shijuebackup&_sid=oy3YUv2xWEHzE18A0NRN005500"


#!/bin/bash

# ==============================================================================
# VS Code 다중 프로필 자동 조립 스크립트 (Lego-style Builder)
# ==============================================================================

export LANG="ko_KR.UTF-8"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/profiles_data"
PROFILES_DB="$HOME/AppData/Roaming/Code/User/globalStorage/storage.json"

echo "🚀 VS Code 프로필 자동 조립 스크립트를 시작합니다..."

# 1. 필수 의존성(jq) 체크
if ! command -v jq &> /dev/null; then
    echo "⚙️ 'jq'가 설치되어 있지 않아 자동 설치를 진행합니다..."
    winget.exe install jqlang.jq --accept-source-agreements --accept-package-agreements
    if ! command -v jq &> /dev/null; then
        echo "⚠️ [주의] jq 설치 후 터미널을 완전히 껐다가 다시 실행해 주세요."
        exit 1
    fi
    echo "✅ jq 설치 완료!"
fi

# ==============================================================================
# [핵심 로직] 프로필 조립 함수
# ==============================================================================
build_profile() {
    local PROFILE_NAME="$1"
    shift 
    local MODULES=("$@")
    local FILE_PATHS=()

    echo -e "\n=================================================="
    echo "🛠️  [$PROFILE_NAME] 프로필 구축을 시작합니다."
    echo "📦 로드된 모듈: ${MODULES[*]}"
    echo "--------------------------------------------------"

    # [디버깅] 모듈 파일 존재 여부 확인
    echo -n "⏳ [1/4] 모듈 파일 유효성 검사 중... "
    for MOD in "${MODULES[@]}"; do
        local TARGET_FILE="$DATA_DIR/${MOD}.json"
        if [ ! -f "$TARGET_FILE" ]; then
            echo "❌ 실패!"
            echo "  -> [오류] 파일을 찾을 수 없습니다: $TARGET_FILE"
            return 1
        fi
        FILE_PATHS+=("$TARGET_FILE")
    done
    echo "✅ 완료"

    # [디버깅] 프로필 생성 및 경로 탐색
    echo -n "⏳ [2/4] VS Code 프로필 내부 DB 탐색 중... "
    code --profile "$PROFILE_NAME" --list-extensions > /dev/null
    sleep 1 # VS Code가 profiles.json을 갱신할 시간을 잠시 벌어줍니다.

    local LOCATION_URI=$(jq -r ".userDataProfiles[] | select(.name == \"$PROFILE_NAME\") | .location" "$PROFILES_DB" 2>/dev/null)
    
    if [ -n "$LOCATION_URI" ] && [ "$LOCATION_URI" != "null" ]; then
        local PROFILE_ID=$(basename "$LOCATION_URI")
        local PROFILE_DIR="$HOME/AppData/Roaming/Code/User/profiles/$PROFILE_ID"
        local SETTINGS_PATH="$PROFILE_DIR/settings.json"
        echo "✅ 완료 ($PROFILE_ID)"

        # [디버깅] 설정 병합
        echo -n "⏳ [3/4] settings.json 딥 머지(Deep Merge) 진행 중... "
        jq -s 'reduce .[] as $item ({}; . * ($item.settings // {}))' "${FILE_PATHS[@]}" > "$SETTINGS_PATH"
        echo "✅ 완료"
    else
        echo "❌ 실패!"
        echo "  -> [경고] profiles.json에서 $PROFILE_NAME 경로를 찾을 수 없습니다."
        return 1
    fi

    # [디버깅] 확장 프로그램 병합 및 설치 진행률 표시
    echo "⏳ [4/4] 확장 프로그램 병합 및 설치 시작..."
    
    # 확장 프로그램 목록을 Bash 배열로 저장하여 전체 개수 파악
    local EXTENSIONS_ARRAY=($(jq -r -s '[.[].extensions // []] | flatten | unique | .[]' "${FILE_PATHS[@]}"))
    local TOTAL_EXT=${#EXTENSIONS_ARRAY[@]}
    local COUNT=1

    echo "  -> 총 $TOTAL_EXT 개의 고유 확장 프로그램이 식별되었습니다."

    for EXT in "${EXTENSIONS_ARRAY[@]}"; do
        if [ -n "$EXT" ]; then
            # 진행률 표시 (예: [3/15] 설치 중: ext.name ...)
            echo -ne "  👉 [$COUNT/$TOTAL_EXT] $EXT 설치 중... "
            
            # 오류 출력은 숨기지 않고, 정상 출력만 숨김 처리하여 에러 발생 시 추적 가능하게 함
            if code.cmd --profile "$PROFILE_NAME" --install-extension "$EXT" --force > /dev/null 2>&1; then
                echo "✅"
            else
                echo "❌ (설치 실패)"
            fi
        fi
        ((COUNT++))
    done

    echo "🎉 [$PROFILE_NAME] 세팅이 성공적으로 완료되었습니다!"
}

# ==============================================================================
# [데이터 주입부] 
# ==============================================================================

BASE_ENV=("mod_Base" "mod_Windows")

PYTHON_MODULES=("${BASE_ENV[@]}" "mod_Workspace" "mod_DataServer" "mod_Workflow" "mod_Python")
build_profile "Dev_Python" "${PYTHON_MODULES[@]}"

# CPP_MODULES=("${BASE_ENV[@]}" "mod_Workspace" "mod_Workflow" "mod_Cpp")
# build_profile "Dev_Cpp" "${CPP_MODULES[@]}"

# LATEX_MODULES=("${BASE_ENV[@]}" "mod_Workspace" "mod_Workflow" "mod_LaTeX")
# build_profile "Dev_LaTeX" "${LATEX_MODULES[@]}"

echo -e "\n🚀 모든 작업이 끝났습니다. VS Code를 실행하여 확인해 보세요!"
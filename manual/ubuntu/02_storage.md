# Ubuntu 스토리지 관리 매뉴얼

Utility Belt의 스토리지 관리 모듈은 복잡한 리눅스 스토리지 설정(`fstab`, `mount`, `lvm`, `parted` 등)을 "프로필(Profile)"이라는 개념으로 추상화하여 관리합니다. 사용자는 UI를 통해 원하는 상태(프로필)를 정의하고, 이를 "적용(Apply)"하는 방식으로 스토리지를 관리합니다.

## 1. 개요

- **파일 위치**:
  - UI 스크립트: `ui/ubuntu/proc_storage.sh`
  - 백엔드 로직: `script/system/ubuntu/02_storage.sh`
  - 설정 파일: `template/ubuntu_config.conf` (또는 실행 시 지정된 설정 파일)
- **주요 기능**:
  - Direct Profile: 단일 디스크 전체 사용.
  - LVM Profile: 볼륨 그룹(VG) 및 논리 볼륨(LV) 구성.
  - CIFS Profile: Windows/NAS 네트워크 공유 폴더 마운트.
  - 상태 조회: 현재 디스크 및 마운트 상태 시각화.

## 2. 사용 방법

메인 메뉴에서 **Storage Management**를 선택하여 진입합니다.

### A. 프로필 생성 (Create Profile)

#### 1. Direct Profile (단일 디스크)
디스크 하나를 통째로 포맷하여 특정 경로에 마운트할 때 사용합니다.
- **Source Disk**: `/dev/sdb`와 같은 물리 디스크 경로를 입력합니다.
- **Mount Point**: `/mnt/data`와 같은 마운트 경로를 입력합니다.
- **특징**: 파티션 크기는 자동으로 디스크의 **100%**로 설정됩니다.

#### 2. LVM Profile (논리 볼륨 관리)
유연한 스토리지 관리가 필요할 때 사용합니다.
- **VG Name**: 볼륨 그룹 이름을 지정합니다.
- **PV Selection**: 체크리스트에서 VG에 포함할 물리 디스크들을 선택합니다.
- **LV Configuration**: 생성할 논리 볼륨의 이름, 크기(예: `100%FREE`), 파일시스템, 마운트 포인트를 설정합니다.

#### 3. CIFS Profile (네트워크 공유)
SMB/CIFS 프로토콜을 사용하는 원격 스토리지를 연결합니다.
- **Remote Info**: 서버 IP와 공유 폴더 이름을 입력합니다.
- **Credential**: 접속에 필요한 사용자명과 비밀번호를 입력하면, 보안을 위해 별도의 파일(`~/.smbcredentials_*`)로 안전하게 저장됩니다.

### B. 프로필 적용 및 해제 (Apply/Unmount)

**"Apply/Unmount Profiles"** 메뉴에서 생성된 프로필들의 상태를 관리합니다.

1. **목록 확인**: 현재 설정 파일에 정의된 모든 프로필이 표시됩니다.
   - 이미 마운트된 프로필은 상태가 `ON`으로 표시됩니다.
2. **체크/해제**:
   - **체크(V)**: 해당 프로필을 시스템에 **적용(Mount)**합니다. 포맷이 필요한 경우 자동으로 수행됩니다.
   - **해제( )**: 해당 프로필을 시스템에서 **제거(Unmount)**합니다.
3. **실행**: 확인을 누르면 변경 사항이 일괄 적용되며, `/etc/fstab`이 업데이트되어 재부팅 후에도 유지됩니다.

## 3. 고급 설정 (설정 파일 직접 수정)

UI에서 지원하지 않는 복잡한 구성은 설정 파일을 직접 수정하여 구현할 수 있습니다.

### 설정 파일 예시

```ini
[STORAGE_PROFILE_datalake]
PROFILE_TYPE="lvm"
VG_NAME="vg_data"
VG_DEVICES="/dev/sdb /dev/sdc"

# RAID 0 구성 예시
DEFINE_LV_stripe_vol="type=raid0; size=100%FREE; devices=/dev/sdb /dev/sdc"
MOUNT_TARGET="stripe_vol"
MOUNT_POINT="/mnt/datalake"
FSTYPE="xfs"
```

## 4. 주의 사항

- **데이터 초기화**: Direct 및 LVM 프로필을 **처음 적용**할 때, 해당 디스크나 볼륨이 포맷되어 **데이터가 삭제**될 수 있습니다. (이미 포맷된 경우 건너뜀)
- **Direct 모드**: Direct 모드는 디스크의 기존 파티션을 무시하고 새 파티션을 생성하려 시도하므로, **빈 디스크**나 **초기화해도 되는 디스크**에만 사용하십시오.

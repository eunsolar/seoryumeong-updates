# 서류멍 🐶 Windows 배포 패키지

이 파일들은 `eunsolar/seoryumeong-updates` 저장소에 업로드하기 위한 **소스 코드와 빌드 자동화 설정**입니다.

## 저장소에 올리는 방법
1. 저장소의 **Add file → Upload files**를 선택합니다.
2. 프로젝트 파일과 `.github/workflows/windows-release.yml` 경로를 유지해 업로드합니다. (숨김 폴더 업로드가 어려우면 GitHub 웹 에디터에서 직접 경로를 만들어도 됩니다.)
3. **Releases → Draft a new release**에서 태그 `v4.2.0`을 새로 만들고 Publish release를 누릅니다.
4. **Actions**에서 Windows 빌드가 성공했는지 확인합니다.
5. 성공하면 Release에 `Seoryumeong-Windows.zip`이 자동 첨부됩니다.

## 업데이트 확인
앱의 `업데이트 확인`은 GitHub의 최신 공개 Release API를 읽고 새로운 버전의 다운로드 페이지를 엽니다. **백그라운드 자동 설치는 아직 지원하지 않습니다.** 최초 사용자는 ZIP에서 `Seoryumeong.exe`를 꺼내 실행합니다. 바탕화면 바로가기를 고정 경로에 생성하고 싶다면 EXE를 고정 폴더에 두고 Windows의 `바로 가기 만들기`를 이용하세요.

## 주의사항
- 주민등록번호 및 계좌번호 원본·출력 엑셀은 절대 저장소에 올리지 마세요.
- 주민등록번호를 처리할 법적 권한이 있는 업무에서만 사용하고, 결과 파일의 접근을 제한하세요.
- OCR이 인식한 번호는 원본과 수동 대조하세요.
- OCR 이미지 처리는 Windows용 Tesseract OCR (kor+eng)을 별도 설치해야 합니다.
- 이 소스는 Linux에서 구문 검사를 했지만 Windows 빌드 및 실제 문서의 인식 정확도는 검증하지 않았습니다.

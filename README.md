# Korean Food & Drinks (DayZ mod)

한국 음식·음료를 DayZ에 추가하는 모드의 코드와 설정입니다.
Code and configuration for a DayZ mod that adds Korean food and drinks.

- Steam Workshop: https://steamcommunity.com/sharedfiles/filedetails/?id=3806858083
- Author: gomgril
- DayZ 1.29

## 이 저장소에 있는 것 / What's here

| 경로 | 내용 |
|---|---|
| `source/KF_Food`, `source/KF_Pantry` | 두 애드온의 `config.cpp`, 스크립트(`scripts/4_World`), `model.cfg`, 재질(`*.rvmat`), 번역(`KF_Food/stringtable.csv`) |
| `l10n/` | 번역 원본(`strings.tsv`, `tr-*.tsv`)과 `stringtable.csv` 생성기 |
| `make-types.ps1` | 서버 스폰 설정(`types_koreanfood.xml`) 생성기 |
| `repack.ps1` | 기존 PBO의 모델은 그대로 두고 텍스트 파일만 바꿔 다시 패킹·서명 |
| `build-full.ps1` | 모델까지 전부 변환(Binarize)해 빌드 |
| `@KoreanFood/` | 배포 폴더의 `mod.cpp`, `PERMISSIONS.txt`, `THIRD_PARTY_NOTICES.txt`, `extras/types_koreanfood.xml` |
| `Workshop-*.txt` | 창작마당 설명과 변경 사항 |

## 이 저장소에 없는 것 / Not included

모델(`.p3d`), 텍스처(`.paa`), 실제 제품 포장 이미지, 애니메이션·사운드 파일, 빌드된 PBO, 서명키는 올리지 않습니다.
제품 포장 디자인과 상표는 각 회사에 권리가 있습니다. 게임에서 쓰려면 창작마당 버전을 받으세요.

Models, textures, real product packaging images, animation/sound binaries, built PBOs and signing keys are not in this repository.
Product packaging and trademarks belong to their respective owners. Use the Workshop release to play.

## 번역 수정 / Editing translations

1. `l10n/strings.tsv`(한국어·영어) 또는 `l10n/tr-<언어>.tsv`를 고칩니다.
2. `l10n/make-stringtable.ps1`을 실행하면 `source/KF_Food/stringtable.csv`가 다시 만들어집니다.
   DayZ는 한 칸이 255바이트를 넘으면 그 언어 전체를 읽지 않으므로, 생성기가 250바이트를 넘는 문장을 거부합니다.

## 재배포 / Redistribution

리팩·모드팩 포함은 자유입니다. 조건은 `@KoreanFood/PERMISSIONS.txt`를 보세요.
Repacks and modpacks are allowed; see `@KoreanFood/PERMISSIONS.txt`.

## AI 활용 / Use of AI

이 모드는 코딩 경험 없이 AI를 활용해 만들고 있습니다. 코드·모델·텍스처·번역 등 기술 작업은 AI가 진행했습니다.
This mod is made with AI assistance by an author without coding experience; the technical work (code, models, textures, translation) was done with AI.

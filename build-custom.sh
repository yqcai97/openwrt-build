#!/bin/bash
# ============================================================
# OpenWrt 定制固件自动构建脚本（ImageBuilder 方案 · 科学上网版）
# 用法:  chmod +x build-custom.sh && ./build-custom.sh
# 前置:  Linux 环境（WSL/云主机）+ ~10GB 磁盘
# 产物:  ./bin/*.img.gz
# ============================================================
set -e
set -o pipefail

# ============ 配置区（按需修改）============
RELEASE="23.05.5"                  # OpenWrt 版本
TARGET="x86/64"                    # 目标平台（软路由默认 x86_64）
PROFILE="generic"                  # 设备 Profile（x86 用 generic；ARM 设备填型号）
# 镜像站：默认阿里（国内稳定）；可换 https://mirrors.tuna.tsinghua.edu.cn/openwrt 或官方
MIRROR="https://mirrors.aliyun.com/openwrt"
# 第三方插件源（openclash；GitHub 仓库，需要能访问 GitHub 的网络）
FEED_KIDDIN9="https://github.com/kiddin9/openwrt-packages.git"
FEED_OPENCLASH="https://github.com/vernesong/OpenClash.git"
# ============================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
BIN_DIR="$SCRIPT_DIR/bin"
mkdir -p "$BUILD_DIR" "$BIN_DIR"
cd "$BUILD_DIR"

echo "===== 1/5 下载 ImageBuilder ($RELEASE $TARGET) ====="
ARCH=$(echo "$TARGET" | tr '/' '-')
# 注意：23.05.x 的 ImageBuilder 文件名是 .Linux-x86_64（大写 L），勿改错
URL="$MIRROR/releases/$RELEASE/targets/$TARGET/openwrt-imagebuilder-$RELEASE-$ARCH.Linux-x86_64.tar.xz"
echo "下载: $URL"
wget -q --show-progress -c "$URL" -O ib.tar.xz || {
  echo "主源下载失败，尝试清华镜像..."; 
  wget -q --show-progress -c "https://mirrors.tuna.tsinghua.edu.cn/openwrt/releases/$RELEASE/targets/$TARGET/openwrt-imagebuilder-$RELEASE-$ARCH.Linux-x86_64.tar.xz" -O ib.tar.xz
}
tar -xf ib.tar.xz
IB_DIR=$(ls -d openwrt-imagebuilder-* | head -1)
cd "$IB_DIR"

echo "===== 2/5 添加 openclash 第三方插件源 ====="
echo "src-git kiddin9 $FEED_KIDDIN9" >> feeds.conf.default
echo "src-git openclash $FEED_OPENCLASH" >> feeds.conf.default
# 更新并安装 feeds（GitHub 网络不佳时可能失败，失败不中断主流程）
./scripts/feeds update -a > feeds-update.log 2>&1 || echo "（feeds update 部分失败，见 feeds-update.log）"
./scripts/feeds install -a > feeds-install.log 2>&1 || echo "（feeds install 部分失败，见 feeds-install.log）"

echo "===== 3/5 编译定制固件 ====="
# 把包源从 downloads.openwrt.org 换成阿里镜像（官方源在本网络不可达）
sed -i 's|https://downloads.openwrt.org|https://mirrors.aliyun.com/openwrt|g' repositories.conf
# 放入预编译的 openclash .ipk（packages/ 目录会被 ImageBuilder 自动收录）
mkdir -p packages
cp -f "$SCRIPT_DIR"/prebuilt/*.ipk packages/ 2>/dev/null || echo "（无预编译 ipk，跳过）"
ls -la packages/ 2>/dev/null

PACKAGES=$(grep -vE '^\s*#|^\s*$' "$SCRIPT_DIR/packages.list" | tr '\n' ' ')
# FORCE=1：绕过 GNU coreutils 前置检查（Ubuntu 新版默认 uutils coreutils）
make image \
  FORCE=1 \
  PROFILE="$PROFILE" \
  PACKAGES="$PACKAGES" \
  FILES="$SCRIPT_DIR/files" \
  BIN_DIR="$BIN_DIR" \
  2>&1 | tee build.log

echo "===== 4/5 完成 ====="
echo "固件输出目录: $BIN_DIR"
ls -lh "$BIN_DIR"/*.img.gz 2>/dev/null || ls -lh "$BIN_DIR"

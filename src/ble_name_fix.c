/*
 * ZMK Studioなどから一度でもBluetooth名を動的変更すると、その名前が
 * 設定領域(フラッシュ上のsettings)に保存され、以後はアプリのファーム
 * ウェアを書き換えてCONFIG_ZMK_KEYBOARD_NAME(=CONFIG_BT_DEVICE_NAME)を
 * 変えても、起動時にsettingsから復元された古い名前が優先されてしまう
 * (CONFIG_BT_DEVICE_NAME_DYNAMIC=yのため)。settings_resetファーム
 * ウェアはZMK独自のble/*設定のみを消去し、Zephyr標準のbt/name設定は
 * 消去しないため、それだけでは直らない。
 *
 * settings読み込み完了時に必ずコンパイル時の名前を強制的に上書きする
 * ことで、保存された古い名前が残り続ける問題を解消する。
 */
#include <zephyr/init.h>
#include <zephyr/settings/settings.h>

#include <zmk/ble.h>

#if IS_ENABLED(CONFIG_SETTINGS)

static int roba_force_ble_name_commit(void) {
    zmk_ble_set_device_name((char *)CONFIG_BT_DEVICE_NAME);
    return 0;
}

static struct settings_handler roba_force_ble_name_handler = {
    .name = "roba_name_fix",
    .h_commit = roba_force_ble_name_commit,
};

static int roba_force_ble_name_init(void) {
    return settings_register(&roba_force_ble_name_handler);
}

SYS_INIT(roba_force_ble_name_init, APPLICATION, 99);

#endif /* IS_ENABLED(CONFIG_SETTINGS) */

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
#include <zephyr/kernel.h>
#include <zephyr/settings/settings.h>

/* zmk_ble_set_device_name()を含むsrc/ble.cは、ZMKコア側のCMakeLists.txtで
 * 「分割キーボードでない、または中央機(central)である」かつ
 * CONFIG_ZMK_BLEが有効な場合にのみリンクされる。左手(周辺機)や
 * settings_resetのビルドではリンクされないため、同じ条件で囲んで
 * 未定義参照エラーを避ける。 */
#define ROBA_BLE_NAME_FIX_AVAILABLE                                                              \
    (IS_ENABLED(CONFIG_ZMK_BLE) &&                                                               \
     (!IS_ENABLED(CONFIG_ZMK_SPLIT) || IS_ENABLED(CONFIG_ZMK_SPLIT_ROLE_CENTRAL)))

#if IS_ENABLED(CONFIG_SETTINGS) && ROBA_BLE_NAME_FIX_AVAILABLE

#include <zmk/ble.h>

/*
 * h_commitはsettings_load()の呼び出しスタックの中で同期的に実行される。
 * zmk_ble_set_device_name()はbt_set_name()経由でsettings_save_one()を
 * 呼び、settingsへの書き込みを行うため、settings読み込みが完了しきって
 * いないこのタイミングで直接呼ぶと、settingsサブシステムの内部状態/ロックに
 * 再入してしまい、起動がハングする(→ウォッチドッグでリブートを繰り返す)
 * 恐れがある。そのため実際の呼び出しはシステムワークキューに委譲し、
 * settings_load()の呼び出しスタックを抜けた後に実行する。
 */
static void roba_force_ble_name_work_handler(struct k_work *work) {
    zmk_ble_set_device_name((char *)CONFIG_BT_DEVICE_NAME);
}

static K_WORK_DEFINE(roba_force_ble_name_work, roba_force_ble_name_work_handler);

static int roba_force_ble_name_commit(void) {
    k_work_submit(&roba_force_ble_name_work);
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

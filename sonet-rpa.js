(function () {
  'use strict';

  // ボタン表示を許可するグループコード
  const ALLOWED_GROUP = 'Administrators';

  kintone.events.on('app.record.detail.show', async (event) => {
    // 重複生成防止
    if (document.getElementById('apclo-sonet-rpa-btn')) {
      return event;
    }

    // 現在ログインしているユーザーの所属グループを取得
    try {
      const res = await kintone.api(
        kintone.api.url('/v1/user/groups', true),
        'GET',
        { code: kintone.getLoginUser().code }
      );
      const groupCodes = (res.groups || []).map((g) => g.code);
      if (!groupCodes.includes(ALLOWED_GROUP)) {
        return event; // 対象グループ外ならボタン非表示
      }
    } catch (e) {
      console.error('[So-net RPA] グループ取得失敗:', e);
      return event;
    }

    const btn = document.createElement('button');
    btn.id = 'apclo-sonet-rpa-btn';
    btn.textContent = 'So-net 申込実行';
    btn.style.cssText =
      'padding:8px 16px;background:#0066cc;color:#fff;border:none;' +
      'border-radius:4px;cursor:pointer;font-weight:bold;margin-left:8px;';

    btn.onclick = () => {
      const appId = kintone.app.getId();
      const recordId = event.recordId;
      const url = `apclo-sonet://run?app=${appId}&record=${recordId}`;
      console.log('[So-net RPA] Dispatch URL:', url);
      window.location.href = url;
    };

    const headerMenu = kintone.app.record.getHeaderMenuSpaceElement();
    if (headerMenu) {
      headerMenu.appendChild(btn);
    }

    return event;
  });
})();

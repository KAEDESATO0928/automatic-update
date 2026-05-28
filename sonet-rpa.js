(function () {
  'use strict';

  kintone.events.on('app.record.detail.show', (event) => {
    // 既に追加済みなら何もしない（再描画対策）
    if (document.getElementById('apclo-sonet-rpa-btn')) {
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

      // デバッグ表示（URLスキームハンドラ未登録時の動作確認用）
      console.log('[So-net RPA] Dispatch URL:', url);

      // URLスキーム発火
      window.location.href = url;
    };

    const headerMenu = kintone.app.record.getHeaderMenuSpaceElement();
    if (headerMenu) {
      headerMenu.appendChild(btn);
    }

    return event;
  });
})();

# 部署說明

這個專案是 monorepo：`frontend/`（React + Vite 靜態網站）與 `backend/`（FastAPI + SQLAlchemy）。

**Vercel 只能部署 `frontend/` 這種靜態前端**，無法直接跑 FastAPI 這種常駐後端服務。如果只把整個 repo
丟給 Vercel，前端會被建置出來，但送出問卷時呼叫的 API（預設 `http://localhost:8000`，見
`frontend/src/api/client.ts`）在瀏覽器端根本連不到，畫面就會卡在最後一步並顯示「發生錯誤，請稍後再試」。

所以正確部署方式是「前後端分開部署」：

## 1. 部署後端（FastAPI）

後端需要一個能跑常駐 Python 服務的平台，例如 Render、Railway、Fly.io。repo 根目錄已附上
`render.yaml`，可以直接在 Render 用「New +` → `Blueprint」匯入這個 repo 一鍵建立服務，設定如下：

- Root: `backend/`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- 環境變數（對應 `backend/app/config.py`）：
  - `APP_DATABASE_URL`：本機/展示可先用 `sqlite:///./dev.db`；正式環境建議接 Postgres（Render 可
    免費建一個 Postgres 實例，把它的連線字串填進來）。
  - `APP_CORS_ALLOW_ORIGINS`：填上 Vercel 前端的網域，例如
    `https://your-app.vercel.app`（多個網域用逗號分隔）。**這步不能漏**，否則瀏覽器會因為 CORS 被擋。

部署完成後會拿到一個後端網址，例如 `https://ai-financial-advisor-api.onrender.com`。

## 2. 部署前端（Vercel）

repo 根目錄已加上 `vercel.json`，Vercel 會自動用 `cd frontend && npm install && npm run build`
建置，輸出目錄是 `frontend/dist`，不需要額外手動設定 Root Directory。

在 Vercel 專案的 Settings → Environment Variables 加入：

- `VITE_API_URL`：填上第 1 步拿到的後端網址（不要有結尾斜線），例如
  `https://ai-financial-advisor-api.onrender.com`。

**注意：`VITE_API_URL` 是建置期（build-time）就會被 Vite 內嵌進打包檔案的變數**，改了環境變數後要
重新觸發一次 Deploy 才會生效，不是重整頁面就會更新。

## 3. 驗證

1. 打開後端網址 `/health`，應該回傳 `{"status": "ok"}`。
2. 打開部署好的 Vercel 網址，完整跑完問卷三步驟，確認能看到雷達圖結果頁，瀏覽器 DevTools 的
   Network 分頁裡 `POST /assessments` 要打到你設定的後端網址且回傳 200，不是打到
   `localhost:8000`。
3. 若仍卡住並顯示紅字錯誤，先看是哪一種錯誤文字：
   - 「無法連線至伺服器…」：`VITE_API_URL` 沒設對、後端沒啟動，或是 CORS 沒開對網域。
   - 其他訊息：是後端回傳的驗證錯誤，屬於資料格式問題，跟部署設定無關。

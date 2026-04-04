import { useAIStream } from './hooks/useAIStream'
import { Sidebar } from './components/Sidebar/Sidebar'
import { EmailList } from './components/EmailList/EmailList'
import { EmailDetail } from './components/EmailDetail/EmailDetail'

export default function App() {
  // 全局订阅 SSE AI 事件流
  useAIStream()

  return (
    <div className="flex h-screen overflow-hidden bg-white text-gray-900">
      <Sidebar />

      {/* 邮件列表（中栏）*/}
      <div className="flex-1 flex flex-col border-r border-gray-200 h-full min-w-0">
        <EmailList />
      </div>

      {/* 邮件详情（右栏）*/}
      <div className="flex-1 flex flex-col h-full min-w-0">
        <EmailDetail />
      </div>
    </div>
  )
}

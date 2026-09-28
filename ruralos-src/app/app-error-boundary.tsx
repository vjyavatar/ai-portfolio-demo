import React from 'react';
export default class AppErrorBoundary extends React.Component<{children:React.ReactNode},{failed:boolean}>{
 state={failed:false};
 static getDerivedStateFromError(){return {failed:true}}
 render(){return this.state.failed?<section role="alert" className="panel" style={{margin:'24px auto',maxWidth:900}}><h1>This screen could not open</h1><p>A connection problem or app update may have interrupted it. Refresh to load the latest version. Unsaved answers will be cleared.</p><button className="primary" onClick={()=>location.reload()}>Refresh app</button><a className="outline" style={{marginLeft:12}} href="https://rural-family-action-os.vjyrcks.chatgpt.site/">Open secure family app</a></section>:this.props.children}
}

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';

export function Settings() {
    return (
        <div className="max-w-2xl mx-auto space-y-6">
            <div>
                <h1 className="text-3xl font-bold tracking-tight">应用设置</h1>
                <p className="text-muted-foreground mt-1">管理 API 密钥和应用配置。</p>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>API 配置</CardTitle>
                    <CardDescription>
                        后端优先读取系统环境变量，其次读取本地 <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">.env</code>，
                        最后才使用 <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">backend/app/config.py</code> 中的空位默认值。
                        修改后请重启后端服务。
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* OpenAI Section */}
                    <div className="space-y-3">
                        <h4 className="text-sm font-semibold text-foreground">OpenAI 服务</h4>
                        <div className="space-y-2">
                            <Label>OPENAI_API_KEY</Label>
                            <Input
                                type="password"
                                placeholder="推荐在 Mac 环境变量中配置"
                                disabled
                                value="••••••••"
                            />
                            <p className="text-xs text-muted-foreground">
                                同时用于 Prompt 生成和图片生成。推荐通过 <code className="font-mono">export OPENAI_API_KEY=...</code> 配置；
                                也可以写入本地 <code className="font-mono">.env</code>，或在个人 fork 中手动填写 <code className="font-mono">config.py</code> 的空位。
                            </p>
                        </div>
                        <div className="space-y-2">
                            <Label>OPENAI_TEXT_MODEL</Label>
                            <Input
                                type="text"
                                placeholder="gpt-5.5"
                                disabled
                                value="gpt-5.5"
                            />
                            <p className="text-xs text-muted-foreground">
                                用于分析论文并生成结构化配图 Prompt。
                            </p>
                        </div>
                        <div className="space-y-2">
                            <Label>OPENAI_IMAGE_MODEL</Label>
                            <Input
                                type="text"
                                placeholder="gpt-image-2"
                                disabled
                                value="gpt-image-2"
                            />
                            <p className="text-xs text-muted-foreground">
                                用于文生图和图生图编辑。
                            </p>
                        </div>
                    </div>
                </CardContent>
                <CardFooter className="border-t bg-muted/40 p-4">
                    <div className="text-xs text-muted-foreground">
                        提示：修改环境变量或 .env 文件后，请运行 <code className="font-mono bg-muted px-1.5 py-0.5 rounded">uvicorn app.main:app --reload</code> 重启后端。
                    </div>
                </CardFooter>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>数据存储</CardTitle>
                    <CardDescription>应用数据存储在本地文件系统中。</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <Label className="text-muted-foreground">数据库</Label>
                            <p className="mt-1 font-mono text-xs">backend/data/app.db</p>
                        </div>
                        <div>
                            <Label className="text-muted-foreground">上传文件</Label>
                            <p className="mt-1 font-mono text-xs">backend/data/uploads/</p>
                        </div>
                        <div>
                            <Label className="text-muted-foreground">生成图片</Label>
                            <p className="mt-1 font-mono text-xs">backend/data/figures/</p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

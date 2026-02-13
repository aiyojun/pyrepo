((() => {
    const utf8decoder = new TextDecoder('utf8')
    const utf8encoder = new TextEncoder()
    const uuid4 = () => 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });

    const invoke = async (transport, voxe, method, ...args) => {
        const rt = voxe.loads(await transport.request(voxe.dumps(method, ...args)))
        if (rt[0] !== 0)
            throw new Error(rt[1])
        if (rt.length > 2)
            console.warn(`Webview2 remote call expects 1 result, ${rt.length - 1} received`)
        return rt[1]
    }

    class Future {
        promise = null
        resolve = null
        reject = null
        done = false
        result = null
        error = null

        constructor() {
            const self = this
            self.promise = new Promise((resolve, reject) => {
                self.resolve = resolve
                self.reject = reject
            })
        }

        set_exception(err) {
            const self = this
            if (!self.done) {
                clearTimeout(self._tid)
                self.error = err
                if (self.reject) {
                    self.reject(err)
                }
            }
        }

        set_result(rs) {
            const self = this
            self.result = rs
            if (!self.done) {
                clearTimeout(self._tid)
                if (self.resolve) {
                    self.resolve(rs)
                }
            }
        }

        _tid = null

        wait_for(timeoutMs) {
            const self = this
            if (timeoutMs > 0) {
                const p2 = new Promise((resolve, reject) => {
                    self._tid = setTimeout(() => {
                        if (!self.done) {
                            reject(new Error("Timeout"))
                            self.done = true
                        } else {
                            resolve(self.result)
                        }
                        self._tid = null
                    }, timeoutMs)
                })
                return Promise.race([self.promise, p2])
            } else {
                return self.promise
            }
        }
    }

    class Transport {
        // shared resource
        rmemo = null
        wmemo = null
        chunk = 0
        futures = new Map()
        futures_ack = new Map()

        constructor() {
            const self = this
            const webview = window.chrome.webview
            webview.addEventListener("message", e => self.on_listen(e.data))
            webview.addEventListener("sharedbufferreceived", e => {
                if (e.additionalData && e.additionalData.type === "read") {
                    self.rmemo = e.getBuffer();
                } else {
                    self.wmemo = e.getBuffer();
                    self.chunk = self.wmemo.byteLength
                }
            })
        }

        // package
        reqid = null
        pkgid = null
        total = 0
        offset = 0
        cache = null
        cu8view = null

        on_listen(data) {
            try {
                const self = this
                const u8view = new Uint8Array(self.rmemo, 0, self.rmemo.byteLength)
                data = JSON.parse(data)
                if (!Object.hasOwn(data, "type")) return
                const type = data["type"]
                if (type === "ack") {
                    const pkgid = data["pkgid"]
                    if (self.futures_ack.has(pkgid))
                        self.futures_ack.get(pkgid).set_result(1)
                    return
                }
                if (type !== "req") return
                self.pkgid = data["pkgid"]
                if (self.reqid === null || self.reqid !== data["reqid"]) {
                    self.reqid = data["reqid"]
                    self.total = data["total"]
                    self.cache = new ArrayBuffer(self.total)
                    self.cu8view = new Uint8Array(self.cache)
                    self.offset = 0
                }
                const size = data["size"]
                self.cu8view.set(size === this.chunk ? u8view : u8view.slice(0, size), self.offset)
                self.offset += size
                window.chrome.webview.postMessage(JSON.stringify({type: "ack", reqid: self.reqid, pkgid: self.pkgid}))
                // if (self.offset >= self.total) {
                //     console.info("[CACHE]", self.reqid, self.futures.has(self.reqid), new Uint8Array(self.cache))
                // }
                if (self.offset >= self.total && self.futures.has(self.reqid)) {
                    self.futures.get(self.reqid).set_result(new Uint8Array(self.cache))
                    self.reqid = null
                    self.cache = null
                    self.cu8view = null
                }
            } catch (e) {
                console.error(e)
            }
        }

        async send(bufferArray, reqid = null) {
            if (!(bufferArray instanceof BufferArray))
                throw new Error("Transport::send only support BufferArray")
            const self = this
            const chunk = self.wmemo.byteLength
            const u8view = new Uint8Array(self.wmemo, 0, self.wmemo.byteLength)
            if (reqid === null) reqid = uuid4().replace(/-/g, "")
            const size = bufferArray.size
            let pb = 0, pe = 0
            while (pb < size) {
                pe = pb + chunk
                if (pe > size) {
                    pe = size
                }
                const ack = new Future()
                const pkgid = uuid4().replace(/-/g, "")
                self.futures_ack.set(pkgid, ack)
                u8view.set(bufferArray.slice(pb, pe), 0)
                try {
                    window.chrome.webview.postMessage(JSON.stringify({type: "req", reqid, pkgid, total: size, size: pe - pb}))
                    await ack.wait_for(-1)
                } catch (e) {
                    console.error(e)
                } finally {
                    self.futures_ack.delete(pkgid)
                }
                pb = pe
            }
        }

        async request(data, timeoutMs=-1) {
            if (data instanceof ArrayBuffer)
            {
                const bufferArray = new BufferArray()
                bufferArray.push(data)
                data = bufferArray
            }
            const self = this
            const reqid = uuid4().replace(/-/g, "")
            const future = new Future()
            self.futures.set(reqid, future)
            await self.send(data, reqid)
            try {
                return await future.wait_for(timeoutMs)
            } catch (e) {
                throw e
            } finally {
                self.futures.delete(reqid)
            }
        }
    }

    class BufferArray {
        array = []
        size = 0
        indices = []
        clear() {
            this.array = []
            this.size = 0
            this.indices = []
            return this
        }
        push(bytes) {
            if (!(bytes instanceof ArrayBuffer))
                throw new Error("BufferArray::push only support ArrayBuffer")
            this.array.push(bytes)
            this.indices.push(this.size)
            this.size += bytes.byteLength
            return this
        }
        slice(begin, end) {
            if (begin > this.size || begin >= end || end < 0)
                return new Uint8Array(0);
            if (begin < 0) begin = 0;
            if (end > this.size) end = this.size;
            const u8a = new Uint8Array(end - begin);
            let offset = 0
            let status = 0
            for (let i = 0; i < this.indices.length; i++) {
                const b = this.indices[i], e = i === this.indices.length - 1 ? this.size : this.indices[i + 1];
                const buf = new Uint8Array(this.array[i])
                if (begin >= b && begin < e) {
                    if (end > b && end <= e) {
                        u8a.set(buf.slice(begin - b, end - b), 0)
                        break
                    } else {
                        const item = buf.slice(begin - b)
                        u8a.set(item, 0)
                        offset += item.byteLength
                    }
                    status = 1;
                    continue
                }
                if (end > b && end <= e) {
                    const item = buf.slice(0, end - b)
                    u8a.set(item, offset)
                    break
                }
                if (status === 1) {
                    const item = buf
                    u8a.set(item, offset)
                    offset += item.byteLength
                }
            }
            return u8a
        }
    }

    class Voxe {
        dumps(...args) {
            const bytesArray = new BufferArray()
            let buffer, u8view, rwview;
            for (const arg of args) {
                if (arg instanceof Uint8Array) {
                    buffer = new ArrayBuffer(8 + arg.byteLength);
                    u8view = new Uint8Array(buffer, 0, buffer.byteLength)
                    rwview = new DataView(buffer);
                    u8view.set([0, 9, 0])
                    rwview.setUint32(3, args.byteLength)
                    rwview.setUint8(7, 0)
                    u8view.set(arg, 8)
                } else if (typeof arg === 'string') {
                    const str = utf8encoder.encode(arg)
                    buffer = new ArrayBuffer(8 + str.byteLength);
                    u8view = new Uint8Array(buffer, 0, buffer.byteLength)
                    rwview = new DataView(buffer);
                    u8view.set([0, 6, 0], 0)
                    rwview.setUint32(3, str.byteLength)
                    rwview.setUint8(7, 0)
                    u8view.set(str, 8)
                } else if (typeof arg === 'number' && `${arg}`.indexOf('.') > -1) {
                    buffer = new ArrayBuffer(7);
                    u8view = new Uint8Array(buffer, 0, buffer.byteLength)
                    rwview = new DataView(buffer);
                    u8view.set([0, 3, 0])
                    rwview.setFloat32(3, arg)
                } else if (typeof arg === 'number') {
                    buffer = new ArrayBuffer(7);
                    u8view = new Uint8Array(buffer, 0, buffer.byteLength)
                    rwview = new DataView(buffer);
                    u8view.set([0, 2, 0])
                    rwview.setInt32(3, arg)
                } else if (typeof arg === 'boolean') {
                    buffer = new ArrayBuffer(4);
                    u8view = new Uint8Array(buffer, 0, buffer.byteLength)
                    u8view.set([0, 0, 0, arg ? 1 : 0])
                } else if (arg === null) {
                    buffer = new ArrayBuffer(3);
                    u8view = new Uint8Array(buffer, 0, buffer.byteLength)
                    u8view.set([0, 7, 0])
                } else {
                    throw new Error("voxe error")
                }
                bytesArray.push(buffer)
            }
            return bytesArray
        }
        loads(u8view) {
            const buffer = u8view.buffer;
            const rwview = new DataView(buffer);
            let beginIndex = 0
            const arr = []
            while (beginIndex < u8view.length) {
                if (u8view[beginIndex] !== 0) break
                const datatype = u8view[beginIndex + 1]
                if (datatype === 0) {
                    arr.push(!!u8view[beginIndex + 3])
                    beginIndex += 4
                } else if (datatype === 7) {
                    arr.push(null)
                    beginIndex += 3
                } else if (datatype === 2) {
                    arr.push(rwview.getInt32(beginIndex + 3))
                    beginIndex += 7
                } else if (datatype === 3) {
                    arr.push(rwview.getFloat32(beginIndex + 3))
                    beginIndex += 7
                } else if (datatype === 6) {
                    const stringLength = rwview.getUint32(beginIndex + 3)
                    const s = utf8decoder.decode(u8view.slice(beginIndex + 8, beginIndex + 8 + stringLength))
                    arr.push(s)
                    beginIndex += 8 + stringLength
                } else if (datatype === 9) {
                    const stringLength = rwview.getInt32(beginIndex + 3)
                    const s = u8view.slice(beginIndex + 8, beginIndex + 8 + stringLength)
                    arr.push(s)
                    beginIndex += 8 + stringLength
                } else {
                    throw new Error("voxe error")
                }
            }
            return arr
        }
    }
})())
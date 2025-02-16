# coding=utf-8
# python3
import os
import json
import sys
from optparse import OptionParser

def hum_convert(value):
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = 1024.0
    for i in range(len(units)):
        if (value / size) < 1:
            return "%.2f %s" % (value, units[i])
        value = value / size
        
def get_dYSM_uuid(path):
    cmd = "xcrun dwarfdump --uuid "+ path
    a = os.popen(cmd)
    uuids = a.read().strip().lower().replace('-', '').split(" ")
    return uuids[1]

class OOMAnalyzer(object):

    def __init__(self, inputDir, logFileUrl, appDsymPath=None):
        self.inputDir = inputDir
        self.logFileUrl = logFileUrl
        self.appDsymPath = appDsymPath

    def run(self):
        # 转换trace文件为json文件
        print("========转换log文件为json对象")
        logFilePath = self.logFileUrl
        f = open(logFilePath, mode="r")
        contentStr = f.read()
        logJson = json.loads(contentStr)
        f.close()

        # 解析数据
        self.parseLog(logJson)

        print("Done")

    def parseLog(self, logJson):
        # 解析获取所有的Offsets
        uuid2Offsets = self.parseOffsets(logJson)

        # Head
        head = logJson["head"]
        app_uuid = head["app_uuid"]
        print(f"app_uuid:{app_uuid}")
        
        if len(self.appDsymPath) > 0:
            app_uuid = get_dYSM_uuid(self.appDsymPath)
            print(f"used dYSM uuid：[{app_uuid}]")

        # 解析当前APP的符号
        curAppOffsets = uuid2Offsets.get(app_uuid)
        
        if curAppOffsets is None:
            print(f"not match [{app_uuid}]")
            return
        print(f"curAppOffsets={len(curAppOffsets)}")
        address2SymMap = self.symbolictedAddress(self.appDsymPath, curAppOffsets)
        print(f"address2SymMap={len(address2SymMap)}")

        # 重新构造结果
        self.recreateLog(logJson, app_uuid, address2SymMap)

        # 保存结果
        outputPath = "%s_%s" % (os.path.splitext(self.logFileUrl)[0], "_OOM_Symbolicated.json")
        fo = open(outputPath, "w")
        fo.write(json.dumps(logJson, indent=4, ensure_ascii=False))
        fo.close()

        print("Done")

    #获取所有stacksm->frames里面的uuid和offset
    def parseOffsets(self, logJson):
        # Items 处理
        uuid2Offsets = {}
        datas = logJson["items"]
        for dataItemIdx in range(len(datas)):
            dataItem = datas[dataItemIdx]

            stacks = dataItem.get("stacks")
            if stacks is None:
                continue

            #变量堆载
            for stackIdx in range(len(stacks)):
                stack = stacks[stackIdx]
                frames = stack["frames"]
                for frameIdx in range(len(frames)):
                    frame = frames[frameIdx]
                    uuid = frame["uuid"]
                    offset = frame["offset"]

                    uuids = uuid2Offsets.get(uuid)
                    if uuids is None:
                        uuids = []
                        uuid2Offsets[uuid] = uuids

                    try:
                        uuids.index(offset)
                    except ValueError:
                        uuids.append(offset)
        print("stacksm->frames 处理结果 uuid 数量 %d" % len(uuid2Offsets.keys()))
        return uuid2Offsets

    def symbolictedAddress(self, dsymPath, addresses, loadAddress="", isSlide=True):
        allAddressStr = ""
        for address in addresses:
            if isSlide:
                addressInt = int(address) + 0x100000000
                allAddressStr += ("%s " % hex(addressInt))
            else:
                allAddressStr += ("%s " % address)

        if isSlide:
            cmd = "atos -o %s -l %s %s " % (dsymPath, "0x100000000", allAddressStr)
        else:
            cmd = "atos -o %s -l %s %s " % (dsymPath, loadAddress, allAddressStr)

        # res = os.system()
        a = os.popen(cmd)
        res = a.read()

        symbols = res.split("\n")

        address2SymMap = {}
        print(f"symbolictedAddress={len(addresses)}")
        for i in range(len(addresses)):
            address2SymMap[addresses[i]] = symbols[i]

        return address2SymMap

    def recreateLog(self, logJson, destUuid, address2SymMap):
        # Items 处理
        uuid2Offsets = {}
        datas = logJson["items"]
        for dataItemIdx in range(len(datas)):
            dataItem = datas[dataItemIdx]

            # Size
            size = dataItem.get("size", 0)
            sizeStr = hum_convert(size)
            if sizeStr is not None:
                dataItem["size"] = sizeStr

            # Stacks
            stacks = dataItem.get("stacks")
            if stacks is None:
                continue

            for stackIdx in range(len(stacks)):
                stack = stacks[stackIdx]
                frames = stack["frames"]
                stackSize = stack["size"]
                StackSizeStr = hum_convert(stackSize)
                if StackSizeStr is not None:
                    stack["size"] = StackSizeStr
                symbolictedFrames = []
                for frameIdx in range(len(frames)):
                    frame = frames[frameIdx]
                    uuid = frame["uuid"]
                    offset = frame["offset"]
                    if destUuid == uuid:
                        symbolictedFrame = address2SymMap.get(offset)
                        if symbolictedFrame is not None:
                            symbolictedFrames.append(symbolictedFrame)
                stack["frames"] = symbolictedFrames


def main(argv):
    parser = OptionParser('usage: %prog -d <directory_path> -r <远程服务器Host>')
    parser.add_option("-d", "--dir", dest="dir", help="包含.appletrace的文件夹")
    parser.add_option("-u", "--file-url", dest="fileUrl", help="日志文件路径")

    (options, args) = parser.parse_args()
    if options.dir is None:
        parser.print_help()
        return

    if options.remoteHost is None:
        parser.print_help()
        return

    processor = OOMAnalyzer(options.dir, options.fileUrl)
    processor.run()


def test_OOMAnalyzer():
    # 使用时请正确配置 inputDir、logFileUrl、dsymPath 路径
    inputDir = r"/Users/hope/Desktop/Crash"
    logFileUrl = r"/Users/hope/Desktop/Crash/OOM.json"
    dsymPath = r"/Users/hope/Desktop/Crash/MatrixDemo"
    processor = OOMAnalyzer(inputDir, logFileUrl, appDsymPath=dsymPath)
    processor.run()


if __name__ == "__main__":
    # main()
    test_OOMAnalyzer()

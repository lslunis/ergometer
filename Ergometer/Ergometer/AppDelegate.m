#import <AppKit/NSEvent.h>
#import <stdio.h>
#import "AppDelegate.h"

enum {
    ErgoId,
    ErgoKey,
    ErgoMeta,
    ErgoRepeat,
    ErgoMove,
    ErgoClick,
    ErgoScroll,
    ErgoDrag,
    ErgoError
};


@interface AppDelegate ()

@property NSStatusItem *item;
@property NSMutableArray *sample;
@property NSMutableArray *record;
@property NSMutableArray *pastRecords;
@property NSString *recordPath;
@property NSTask *server;
@property NSString *commandPiece;

@end


@implementation AppDelegate

- (long long)sampleId
{
    return (long long)([[NSDate date] timeIntervalSince1970] * 10);
}

- (long long)recordId
{
    return (long long)([[NSDate date] timeIntervalSince1970]);
}

- (void)reset:(NSMutableArray *)array at:(long long)id
{
    [array removeAllObjects];
    array[ErgoId] = @(id);
}

- (void)cycle
{
    long long recordId = [self recordId];
    // If the system clock is adjusted pastward while the program is running, events will
    // be coalesed into a single large interval, maintaining logfile monoticity.
    if (recordId > [self.record[ErgoId] longLongValue]) {
        if (self.record.count > 1) {
            [self.pastRecords addObject:[self.record copy]];
        }
        [self reset:self.record at:recordId];
    }
}

- (BOOL)resampled:(NSUInteger)col sub:(NSUInteger)subcol
{
    if (col < [self.sample count]) {
        NSObject *obj = self.sample[col];
        if ([obj isKindOfClass:[NSMutableArray class]]) {
            NSMutableArray *array = (NSMutableArray *)obj;
            return subcol < [array count] && [array[subcol] isKindOfClass:[NSNumber class]] &&
            !![array[subcol] longLongValue];
        } else {
            return [obj isKindOfClass:[NSNumber class]] && !![(NSNumber *)obj longLongValue];
        }
    }
    return NO;
}

- (void)vivify:(NSMutableArray *)array at:(NSUInteger)index using:(NSUInteger)action
{
    NSUInteger end;
    while ((end = [array count]) <= index) {
        array[end] = @"";
    }
    
    if (action == NSNotFound) {
        long long x = [([array[index] isKindOfClass:[NSNumber class]] ?
                        array[index] : 0) longLongValue];
        array[index] = @(x + 1);
    } else {
        if (![array[index] isKindOfClass:[NSMutableArray class]]) {
            array[index] = [[NSMutableArray alloc] init];
        }
        [self vivify:array[index] at:action using:NSNotFound];
    }
}

- (BOOL)log:(NSArray *)record
{
    NSMutableArray *parts = [[NSMutableArray alloc] init];
    for (NSObject *obj in record) {
        if ([obj isKindOfClass:[NSArray class]]) {
            [parts addObject:[(NSArray *)obj componentsJoinedByString:@" "]];
        } else {
            [parts addObject:[obj description]];
        }
    }
    NSString *string = [[parts componentsJoinedByString:@","] stringByAppendingString:@"\n"];
    
    FILE *file = fopen([[self recordPath] UTF8String], "a");
    if (file == NULL) {
        return NO;
    }
    if (fputs([string UTF8String], file) == EOF) {
        return NO;
    }
    if (fclose(file) == EOF) {
        return NO;
    }
    return YES;
}

- (NSArray*)parse:(NSString *)s
{
    NSArray *lines = [s componentsSeparatedByString:@"\v"];
    NSMutableArray *args = [[NSMutableArray alloc] init];
    for (NSUInteger i = 0; i < lines.count; ++i) {
        args[i] = [lines[i] componentsSeparatedByString:@"\t"];
    }
    return args;
}

- (void)delete:(NSString *)p
{
    [[NSFileManager defaultManager] removeItemAtPath:p error:NULL];
}

- (CGError)fade:(float)t r:(float)r g:(float)g b:(float)b a:(float)a
{
    CGDisplayFadeReservationToken token = kCGDisplayFadeReservationInvalidToken;
    CGError result = CGAcquireDisplayFadeReservation(t, &token);
    if (result != kCGErrorSuccess) {
        return result;
    }
    return CGDisplayFade(token, 0, 0, a, r, g, b, 0);
}

- (void)status:(NSAttributedString*)s
{
    self.item.button.attributedTitle = s;
}

- (void)dispatch:(NSString *)s
{
    NSArray *args = [self parse:s];
    if (args.count >= 2) {
        if ([args[0][0] isEqualToString:@"fade"]) {
            NSArray *xs = (NSArray*)args[1];
            if (xs.count >= 5) {
                [self fade:((NSString*)xs[0]).floatValue r:((NSString*)xs[1]).floatValue g:((NSString*)xs[2]).floatValue b:((NSString*)xs[3]).floatValue a:((NSString*)xs[4]).floatValue];
            }
        }

        if ([args[0][0] isEqualToString:@"status"]) {
            NSMutableAttributedString *b = [[NSMutableAttributedString alloc] init];
            NSArray *strings = (NSArray*)args[1];
            NSUInteger k = MIN(strings.count, args.count - 2);
            for (NSUInteger i = 0; i < k; ++i) {
                NSArray *xs = (NSArray*)args[i + 2];
                NSDictionary *a;
                if (xs.count >= 4) {
                    a = @{NSForegroundColorAttributeName: [NSColor colorWithRed:((NSString*)xs[0]).floatValue green:((NSString*)xs[1]).floatValue blue:((NSString*)xs[2]).floatValue alpha:((NSString*)xs[3]).floatValue]};
                } else {
                    a = @{};
                }
                [b appendAttributedString:[[NSAttributedString alloc] initWithString:strings[i] attributes:a]];
            }
            if (k > 0) {
                [self status:b];
            }
        }
    }
}

- (void)tick
{
    [self cycle];
    int i = 0;
    for (id r in self.pastRecords) {
        if (![self log:r]) {
            break;
        }
        ++i;
    }
    [self.pastRecords removeObjectsInRange:NSMakeRange(0, i)];
}

- (void)listen
{
    NSEventMask mask =
    NSKeyDownMask |
    NSFlagsChangedMask |
    NSLeftMouseDownMask |
    NSRightMouseDownMask |
    NSOtherMouseDownMask |
    NSScrollWheelMask |
    NSMouseMovedMask |
    NSLeftMouseDraggedMask |
    NSRightMouseDraggedMask |
    NSOtherMouseDraggedMask;
    
    [NSEvent addGlobalMonitorForEventsMatchingMask:mask handler:^(NSEvent *e) {
        [self cycle];
        NSUInteger col;
        NSUInteger subcol = NSNotFound;
        NSEventType t = [e type];
        switch (t) {
            case NSKeyDown:
            case NSFlagsChanged:
            {
                col = t == NSKeyDown ? [e isARepeat] ? ErgoRepeat : ErgoKey : ErgoMeta;
                NSUInteger flags = [e modifierFlags];
                subcol =
                !!(flags & NSShiftKeyMask) +
                !!(flags & NSControlKeyMask) +
                !!(flags & NSAlternateKeyMask) +
                !!(flags & NSCommandKeyMask);
                break;
            }
            case NSMouseMoved:
                col = ErgoMove;
                break;
            case NSLeftMouseDown:
            case NSRightMouseDown:
            case NSOtherMouseDown:
                col = ErgoClick;
                break;
            case NSScrollWheel:
                col = ErgoScroll;
                break;
            case NSLeftMouseDragged:
            case NSRightMouseDragged:
            case NSOtherMouseDragged:
                col = ErgoDrag;
                break;
            default:
                col = ErgoError;
        }
        
        
        BOOL shouldVivifyRecord = YES;
        if (col == ErgoRepeat || col == ErgoMove || col == ErgoScroll || col == ErgoDrag) {
            long long sampleId = [self sampleId];
            if (sampleId > [self.sample[ErgoId] longLongValue]) {
                [self reset:self.sample at:sampleId];
            }
            
            if ([self resampled:col sub:subcol]) {
                shouldVivifyRecord = NO;
            } else {
                [self vivify:self.sample at:col using:subcol];
            }
        }
        
        if (shouldVivifyRecord) {
            [self vivify:self.record at:col using:subcol];
        }
    }];
    
    [NSTimer scheduledTimerWithTimeInterval:1 target:self selector:@selector(tick) userInfo:nil repeats:YES];
}

- (void)readCommands:(NSNotification *)notification {
    NSFileHandle *f = [notification object];
    NSString *s = [[NSString alloc] initWithData:[f availableData] encoding:NSUTF8StringEncoding];
    NSMutableArray *commands = [[s componentsSeparatedByString:@"\n"] mutableCopy];
    commands[0] = [self.commandPiece stringByAppendingString:commands[0]];
    self.commandPiece = commands.lastObject;
    [commands removeLastObject];
    for (id command in commands) {
        [self dispatch:command];
    }
    [f waitForDataInBackgroundAndNotify];
}

- (void)applicationDidFinishLaunching:(NSNotification *)notification
{
    NSDictionary *options = @{(__bridge id)kAXTrustedCheckOptionPrompt: @YES};
    Boolean trusted = AXIsProcessTrustedWithOptions((__bridge CFDictionaryRef)options);
    
    self.sample = [[NSMutableArray alloc] init];
    [self reset:self.sample at:[self sampleId]];
    
    self.record = [[NSMutableArray alloc] init];
    [self reset:self.record at:[self recordId]];
    
    self.pastRecords = [[NSMutableArray alloc] init];
    
    NSString *host = [[NSHost currentHost] localizedName];
    NSString *dataDir = [@"~/Library/Application Support/Ergometer" stringByStandardizingPath];
    NSString *recordDir = [dataDir stringByAppendingString:@"/log"];
    self.recordPath = [@[recordDir, @"/", host, @".3.log"] componentsJoinedByString:@""];

    self.item = [[NSStatusBar systemStatusBar] statusItemWithLength:NSVariableStatusItemLength];

    NSString *serverPath = [@[dataDir, @"/src/ergometer.py"] componentsJoinedByString:@""];

    if (trusted && self.item != nil
        && [[NSFileManager defaultManager] createDirectoryAtPath:recordDir withIntermediateDirectories:YES attributes:nil error:NULL]) {

        if ([[NSFileManager defaultManager] isExecutableFileAtPath:serverPath]) {
            self.server = [[NSTask alloc] init];
            [self.server setLaunchPath:serverPath];
            [self.server setArguments:@[@"_", host]];
            NSPipe *pipe = [NSPipe pipe];
            [self.server setStandardOutput:pipe];
            [self.server launch];

            self.commandPiece = @"";
            NSFileHandle *f = [pipe fileHandleForReading];
            [[NSNotificationCenter defaultCenter] addObserver:self selector:@selector(readCommands:) name:NSFileHandleDataAvailableNotification object:f];
            [f waitForDataInBackgroundAndNotify];
        }
        [self listen];
        return;
    }
    
    [[NSApplication sharedApplication] terminate:nil];
}

- (void)applicationWillTerminate:(NSNotification *)notification
{
    [self tick];
    [self.server interrupt];
}

@end

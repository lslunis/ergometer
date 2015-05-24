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
@property NSString *fadePath;
@property NSString *statusPath;
@property NSTask *server;

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

- (NSArray*)parse:(NSString *)p
{
    NSData *x = [[NSFileManager defaultManager] contentsAtPath:p];
    if (x != nil) {
        NSString *s = [[NSString alloc] initWithData:x encoding:NSUTF8StringEncoding];
        if (s != nil) {
            NSArray *lines = [s componentsSeparatedByString:@"\n"];
            NSMutableArray *args = [[NSMutableArray alloc] init];
            for (NSUInteger i = 0; i < lines.count; ++i) {
                args[i] = [lines[i] componentsSeparatedByString:@"\t"];
            }
            return args;
        }
    }
    return @[];
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

- (void)command
{
    NSArray *args = [self parse:self.fadePath];
    if (args.count >= 1) {
        NSArray *xs = (NSArray*)args[0];
        if (xs.count >= 5) {
            CGError result = [self fade:((NSString*)xs[0]).floatValue r:((NSString*)xs[1]).floatValue g:((NSString*)xs[2]).floatValue b:((NSString*)xs[3]).floatValue a:((NSString*)xs[4]).floatValue];
            if (result == kCGErrorSuccess) {
                [self delete:self.fadePath];
            }
        }
    }
    
    args = [self parse:self.statusPath];
    if (args.count >= 1) {
        NSMutableAttributedString *b = [[NSMutableAttributedString alloc] init];
        NSArray *strings = (NSArray*)args[0];
        NSUInteger k = MIN(strings.count, args.count - 1);
        for (NSUInteger i = 0; i < k; ++i) {
            NSArray *xs = (NSArray*)args[i + 1];
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
            [self delete:self.statusPath];
        }
    }
}

- (void)tick
{
    [self command];
    
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
    self.fadePath = [@[dataDir, @"/", host, @".fade.txt"] componentsJoinedByString:@""];
    self.statusPath = [@[dataDir, @"/", host, @".status.txt"] componentsJoinedByString:@""];
    
    NSString *recordDir = [dataDir stringByAppendingString:@"/log"];
    self.recordPath = [@[recordDir, @"/", host, @".3.log"] componentsJoinedByString:@""];

    self.item = [[NSStatusBar systemStatusBar] statusItemWithLength:NSVariableStatusItemLength];

    NSString *serverPath = [@[dataDir, @"/src/ergometer.py"] componentsJoinedByString:@""];

    if (trusted && self.item != nil
        && [[NSFileManager defaultManager] createDirectoryAtPath:recordDir withIntermediateDirectories:YES attributes:nil error:NULL]) {

        if ([[NSFileManager defaultManager] isExecutableFileAtPath:serverPath]) {
            self.server = [NSTask launchedTaskWithLaunchPath:serverPath arguments:@[@"_", host]];
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

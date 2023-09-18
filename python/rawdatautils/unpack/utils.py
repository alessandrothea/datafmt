#general imports
import sys

#dunedaq imports
import daqdataformats
import detdataformats
import fddetdataformats
import trgdataformats
import detchannelmaps

#unpacker imports
from rawdatautils.unpack.dataclasses import *
import rawdatautils.unpack.wibeth
import rawdatautils.unpack.daphne
import h5py

#analysis imports
import numpy as np
import numpy.fft

class Unpacker:

    is_fragment_unpacker = False

    is_detector_unpacker = False
    is_trigger_unpacker = False
    
    def __init__(self, index=None):
        self.index = index

    def get_all_data(self,in_data=None):
        return None

class SourceIDUnpacker(Unpacker):

    is_fragment_unpacker = False

    is_detector_unpacker = False
    is_trigger_unpacker = False

    def get_srcid_data(self,sid):
        return [ SourceIDData(run=self.index.run,
                              trigger=self.index.trigger,
                              sequence=self.index.sequence,
                              src_id=sid.id,
                              subsystem=sid.subsystem,
                              subsystem_str=daqdataformats.SourceID.subsystem_to_string(sid.subsystem),
                              version=sid.version) ]

    def get_all_data(self,in_data):
        #in_data[0]=sid
        #in_data[1]=run
        #in_data[2]=trigger
        #in_data[3]=sequence
        return { "sid": self.get_srcid_data(in_data) }

class TriggerRecordHeaderUnpacker(Unpacker):

    is_fragment_unpacker = False
    
    def get_trh_data(self,trh,n_fragments):
        return [ TriggerRecordData(run=trh.get_run_number(),
                                         trigger=trh.get_trigger_number(),
                                         sequence=trh.get_sequence_number(),
                                         trigger_timestamp_dts=trh.get_trigger_timestamp(),
                                         n_fragments=n_fragments,
                                         n_requested_components=trh.get_num_requested_components(),
                                         error_bits=trh.get_header().error_bits,
                                         trigger_type=trh.get_trigger_type(),
                                         max_sequence_number=trh.get_max_sequence_number(),
                                         total_size_bytes=trh.get_total_size_bytes()) ]

    def get_all_data(self,in_data):
        #in_data[0]=trh
        #in_data[1]=n_fragments
        return { "trh": self.get_trh_data(in_data[0],in_data[1]) }
    
class FragmentUnpacker(Unpacker):

    is_fragment_unpacker = True
    
    is_detector_unpacker = False
    is_trigger_unpacker = False

    def get_n_obj(self,frag):
        return None

    def get_trg_data(self,in_data):
        return None, None

    def get_det_data(self,in_data):
        return None, None, None, None

    def get_frh_data(self,frag):
        frh = frag.get_header()
        return [ FragmentHeaderData(run=frh.run_number,
                                    trigger=frh.trigger_number,
                                    sequence=frh.sequence_number,
                                    src_id=frh.element_id.id,
                                    trigger_timestamp_dts=frh.trigger_timestamp,
                                    window_begin_dts=frh.window_begin,
                                    window_end_dts=frh.window_end,
                                    det_id=frh.detector_id,
                                    error_bits=frh.error_bits,
                                    fragment_type=frh.fragment_type,
                                    total_size_bytes=frh.size,
                                    data_size_bytes=frag.get_data_size()) ]

    def get_all_data(self,in_data):
        #in_data = fragment
        
        data_dict = { "frh": self.get_frh_data(in_data) }
        
        if(self.is_trigger_unpacker):
            trgh, trgd = self.get_trg_data(in_data)
            if trgh is not None: data_dict["trgh"] = trgh
            if trg is not None: data_dict["trgd"] = trgd

        if(self.is_detector_unpacker):
            type_string = type_string = f'{detdataformats.DetID.Subdetector(in_data.get_detector_id()).name}_{in_data.get_fragment_type().name}'
            daqh, deth, detd, detw = self.get_det_data(in_data)
            if daqh is not None: data_dict["daqh"] = daqh
            if deth is not None: data_dict[f"deth_{type_string}"] = deth
            if detd is not None: data_dict[f"detd_{type_string}"] = detd
            if detw is not None: data_dict[f"detw_{type_string}"] = detw

        return data_dict

class TriggerDataUnpacker(FragmentUnpacker):
    
    is_trigger_unpacker = True

    DICT_TRGH_COLS = [
        "n_obj",
        "version"        
    ]
    trg_header_dict_name = "trgh"
    
    def __init__(self,dict_idx):
        super().__init__(dict_idx)

    def get_trg_data_version(self,frag):
        return None

    def get_trg_data_dict(self,frag):
        return None,None

    def get_trg_header_dict(self,frag):
        dict_trgh = dict.fromkeys(self.DICT_TRGH_COLS)
        dict_trgh["version"] = self.get_trg_data_version(frag)
        dict_trgh["n_obj"] = self.get_n_obj(frag)
        return (dict_trgh | self.dict_idx), 1, list(self.dict_idx.keys())


class TriggerPrimitiveUnpacker(TriggerDataUnpacker):

    trg_obj = trgdataformats.TriggerPrimitive
    
    DICT_TP_COLS = [
        "time_start",
        "time_peak",
        "time_over_threshold",
        "channel",
        "adc_integral",
        "adc_peak",
        "detid",
        "type",
        "algorithm",
        "flag"
    ]
    
    def __init__(self,dict_idx):
        super().__init__(dict_idx)

    def get_n_obj(self,frag):
        return frag.get_data_size()/trg_obj.sizeof()
    
    def get_trg_data_dict(self,frag):
        dict_trgd = dict.fromkeys(self.DICT_TP_COLS)

        for i in range(self.n_obj(frag)):
            tp = trg_obj(frag.get_data(i*trg_obj.sizeof()))
        
            dict_trgd["time_start"] = tp.time_start
            dict_trgd["time_peak"] = tp.time_peak
            dict_trgd["time_over_threshold"] = tp.time_over_threshold
            dict_trgd["channel"] = tp.channel
            dict_trgd["adc_integral"] = tp.adc_integral
            dict_trgd["adc_peak"] = tp.adc_peak
            dict_trgd["detid"] = tp.detid
            dict_trgd["type"] = tp.type
            dict_trgd["algorithm"] = tp.algorithm
            dict_trgd["flag"] = tp.flag
            
            return (dict_trgd | self.dict_idx), self.n_obj(frag), list(self.dict_idx.keys())+["channel"]


class DetectorFragmentUnpacker(FragmentUnpacker):
    
    is_detector_unpacker = True

    def __init__(self,ana_data_prescale=1,wvfm_data_prescale=None):
        super().__init__()
        self.ana_data_prescale = ana_data_prescale
        self.wvfm_data_prescale = wvfm_data_prescale
    
    def get_daq_header_version(self,frag):
        return None
    
    def get_det_data_version(self,frag):
        return None

    def get_timestamp_first(self,frag):
        return None
    
    def get_det_crate_slot_stream(self,frag):
        return None, None, None, None

    def get_daq_header_data(self,frag):
        frh = frag.get_header()
        det_id, crate_id, slot_id, stream_id = self.get_det_crate_slot_stream(frag)
        return [ DAQHeaderData(run=frh.run_number,
                               trigger=frh.trigger_number,
                               sequence=frh.sequence_number,
                               src_id=frh.element_id.id,
                               n_obj=self.get_n_obj(frag),
                               daq_header_version=self.get_daq_header_version(frag),
                               det_data_version=self.get_det_data_version(frag),
                               det_id=det_id,
                               crate_id=crate_id,
                               slot_id=slot_id,
                               stream_id=stream_id,
                               timestamp_first_dts=self.get_timestamp_first(frag)) ]
    
    def get_det_header_data(self,frag):
        return None

    def get_det_data_all(self,frag):
        return None, None

    def get_det_data(self,frag):
        det_ana_data, det_wvfm_data = self.get_det_data_all(frag)
        return self.get_daq_header_data(frag), self.get_det_header_data(frag), det_ana_data, det_wvfm_data


class WIBEthUnpacker(DetectorFragmentUnpacker):

    unpacker = rawdatautils.unpack.wibeth
    frame_obj = fddetdataformats.WIBEthFrame
    
    SAMPLING_PERIOD = 32
    N_CHANNELS_PER_FRAME = 64
    
    def __init__(self,channel_map,ana_data_prescale=1,wvfm_data_prescale=None):
        super().__init__(ana_data_prescale=ana_data_prescale,wvfm_data_prescale=wvfm_data_prescale)
        self.channel_map = detchannelmaps.make_map(channel_map)
        
    def get_n_obj(self,frag):
        return self.unpacker.get_n_frames(frag)

    def get_daq_header_version(self,frag):
        return self.frame_obj(frag.get_data()).get_daqheader().version

    def get_timestamp_first(self,frag):
        return self.frame_obj(frag.get_data()).get_timestamp()
    
    def get_det_data_version(self,frag):
        return self.frame_obj(frag.get_data()).get_wibheader().version

    def get_det_crate_slot_stream(self,frag):
        dh = self.frame_obj(frag.get_data()).get_daqheader()
        return dh.det_id, dh.crate_id, dh.slot_id, dh.stream_id

    def get_det_header_data(self,frag):
        frh = frag.get_header()
        wh = self.frame_obj(frag.get_data()).get_wibheader()
        ts_diff_vals, ts_diff_counts = np.unique(np.diff(self.unpacker.np_array_timestamp(frag)),return_counts=True)
        return [ WIBEthHeaderData(run=frh.run_number,
                                  trigger=frh.trigger_number,
                                  sequence=frh.sequence_number,
                                  src_id=frh.element_id.id,
                                  femb_id=(wh.channel>>1)&0x3,
                                  coldata_id=wh.channel&0x1,
                                  version=wh.version,
                                  pulser=wh.pulser,
                                  calibration=wh.calibration,
                                  context=wh.context,
                                  n_channels=self.N_CHANNELS_PER_FRAME,
                                  sampling_period=self.SAMPLING_PERIOD,
                                  ts_diffs_vals=ts_diff_vals,
                                  ts_diffs_counts=ts_diff_counts) ]

    def get_det_data_all(self,frag):
        frh = frag.get_header()
        trigger_number = frh.trigger_number

        get_ana_data = (self.ana_data_prescale is not None and (trigger_number % self.ana_data_prescale)==0)
        get_wvfm_data = (self.wvfm_data_prescale is not None and (trigger_number % self.wvfm_data_prescale)==0)

        if not (get_ana_data or get_wvfm_data):
            return None,None

        ana_data = None
        wvfm_data = None
        
        adcs = self.unpacker.np_array_adc(frag)
        _, crate, slot, stream = self.get_det_crate_slot_stream(frag)
        channels = [ self.channel_map.get_offline_channel_from_crate_slot_stream_chan(crate, slot, stream, c) for c in range(self.N_CHANNELS_PER_FRAME) ]
        planes = [ self.channel_map.get_plane_from_offline_channel(uc) for uc in channels ]
        apas = [ self.channel_map.get_apa_from_offline_channel(uc) for uc in channels ]
        wib_chans = range(self.N_CHANNELS_PER_FRAME)
        
        if get_ana_data:
            adc_mean = np.mean(adcs,axis=0)
            adc_rms = np.std(adcs,axis=0)
            adc_max = np.max(adcs,axis=0)
            adc_min = np.min(adcs,axis=0)
            adc_median = np.median(adcs,axis=0)
            ana_data = [ WIBEthAnalysisData(run=frh.run_number,
                                            trigger=frh.trigger_number,
                                            sequence=frh.sequence_number,
                                            src_id=frh.element_id.id,
                                            channel=channels[i_ch],
                                            plane=planes[i_ch],
                                            apa=apas[i_ch],
                                            wib_chan=wib_chans[i_ch],
                                            adc_mean=adc_mean[i_ch],
                                            adc_rms=adc_rms[i_ch],
                                            adc_max=adc_max[i_ch],
                                            adc_min=adc_min[i_ch],
                                            adc_median=adc_median[i_ch]) for i_ch in range(self.N_CHANNELS_PER_FRAME) ]
        if get_wvfm_data:
            timestamps = self.unpacker.np_array_timestamp(frag)
            ffts = np.abs(np.fft.rfft(adcs,axis=0))
            wvfm_data = [ WIBEthWaveformData(run=frh.run_number,
                                             trigger=frh.trigger_number,
                                             sequence=frh.sequence_number,
                                             src_id=frh.element_id.id,
                                             channel=channels[i_ch],
                                             plane=planes[i_ch],
                                             apa=apas[i_ch],
                                             wib_chan=wib_chans[i_ch],
                                             timestamps=timestamps,
                                             adcs=adcs[:,i_ch],
                                             fft_mag=ffts[:,i_ch]) for i_ch in range(self.N_CHANNELS_PER_FRAME) ]
        
        return ana_data, wvfm_data                


class DAPHNEStreamUnpacker(DetectorFragmentUnpacker):

    unpacker = rawdatautils.unpack.daphne
    frame_obj = fddetdataformats.DAPHNEStreamFrame

    SAMPLING_PERIOD = 1
    N_CHANNELS_PER_FRAME = 4
    
    def get_n_obj(self,frag):
        return self.unpacker.get_n_frames_stream(frag)

    def get_daq_header_version(self,frag):
        return self.frame_obj(frag.get_data()).get_daqheader().version

    def get_timestamp_first(self,frag):
        return self.frame_obj(frag.get_data()).get_timestamp()
    
    def get_det_data_version(self,frag):
        return 0

    def get_det_crate_slot_stream(self,frag):
        dh = self.frame_obj(frag.get_data()).get_daqheader()
        return dh.det_id, dh.crate_id, dh.slot_id, dh.link_id

    def get_det_header_data(self,frag):
        frh = frag.get_header()
        dh = self.frame_obj(frag.get_data()).get_header()
        ts_diff_vals, ts_diff_counts = np.unique(np.diff(self.unpacker.np_array_timestamp(frag)),return_counts=True)
        return [ DAPHNEStreamHeaderData(run=frh.run_number,
                                        trigger=frh.trigger_number,
                                        sequence=frh.sequence_number,
                                        src_id=frh.element_id.id,
                                        n_channels=self.N_CHANNELS_PER_FRAME,
                                        sampling_period=self.SAMPLING_PERIOD,
                                        ts_diffs_vals=self.ts_diff_vals,
                                        ts_diff_counts=self.ts_diff_counts) ]

    def get_det_data_all(self,frag):
        frh = frag.get_header()
        trigger_number = frh.trigger_number

        get_ana_data = (self.ana_data_prescale is not None and (trigger_number % self.ana_data_prescale)==0)
        get_wvfm_data = (self.wvfm_data_prescale is not None and (trigger_number % self.wvfm_data_prescale)==0)

        if not (get_ana_data or get_wvfm_data):
            return None,None

        ana_data = None
        wvfm_data = None

        adcs = self.unpacker.np_array_adc_stream(frag)
        dh = self.frame_obj(frag.get_data()).get_header()
        channels = [ dh.channel_0, dh.channel_1, dh.channel_2, dh.channel_3 ]
        daphne_chans = [ dh.channel_0, dh.channel_1, dh.channel_2, dh.channel_3 ]

        if get_ana_data:
            adc_mean = np.mean(adcs,axis=0)
            adc_rms = np.std(adcs,axis=0)
            adc_max = np.max(adcs,axis=0)
            adc_min = np.min(adcs,axis=0)
            adc_median = np.median(adcs,axis=0)
            ana_data = [ DAPHNEStreamAnalysisData(run=frh.run_number,
                                                  trigger=frh.trigger_number,
                                                  sequence=frh.sequence_number,
                                                  src_id=frh.element_id.id,
                                                  channel=channels[i_ch],
                                                  daphne_chan=daphne_chans[i_ch],
                                                  adc_mean=adc_mean[i_ch],
                                                  adc_rms=adc_rms[i_ch],
                                                  adc_max=adc_max[i_ch],
                                                  adc_min=adc_min[i_ch],
                                                  adc_median=adc_median[i_ch]) for i_ch in range(self.N_CHANNELS_PER_FRAME) ]
        if get_wvfm_data:
            timestamps = self.unpacker.np_array_timestamp_stream(frag)
            ffts = np.abs(np.fft.rfft(adcs,axis=0))
            wvfm_data = [ DAPHNEStreamWaveformData(run=frh.run_number,
                                                   trigger=frh.trigger_number,
                                                   sequence=frh.sequence_number,
                                                   src_id=frh.element_id.id,
                                                   channel=channels[i_ch],
                                                   adcs=adcs[:,i_ch],
                                                   timestamps=timestamps,
                                                   fft_mag=ffts[:,i_ch]) for i_ch in range(self.N_CHANNELS_PER_FRAME) ]
        return ana_data, wvfm_data


class DAPHNEUnpacker(DetectorFragmentUnpacker):

    unpacker = rawdatautils.unpack.daphne
    frame_obj = fddetdataformats.DAPHNEFrame

    SAMPLING_PERIOD = 1
    N_CHANNELS_PER_FRAME = 1
            
    def get_n_obj(self,frag):
        return self.unpacker.get_n_frames(frag)

    def get_daq_header_version(self,frag):
        return self.frame_obj(frag.get_data()).get_daqheader().version

    def get_timestamp_first(self,frag):
        return self.frame_obj(frag.get_data()).get_timestamp()
    
    def get_det_data_version(self,frag):
        return 0

    def get_det_crate_slot_stream(self,frag):
        dh = self.frame_obj(frag.get_data()).get_daqheader()
        return dh.det_id, dh.crate_id, dh.slot_id, dh.link_id

    def get_det_header_data(self,frag):
        return None

    def get_det_data_all(self,frag):
        frh = frag.get_header()
        trigger_number = frh.trigger_number

        get_ana_data = (self.ana_data_prescale is not None and (trigger_number % self.ana_data_prescale)==0)
        get_wvfm_data = (self.wvfm_data_prescale is not None and (trigger_number % self.wvfm_data_prescale)==0)

        if not (get_ana_data or get_wvfm_data):
            return None,None

        n_frames = self.get_n_obj(frag)
        adcs = self.unpacker.np_array_adc(frag)
        daphne_headers = [ self.frame_obj(frag.get_data(iframe*self.frame_obj.sizeof())).get_header() for iframe in range(n_frames) ]
        timestamp = self.unpacker.np_array_timestamp(frag)

        if get_ana_data:

            adc_mean = np.mean(adcs,axis=0)
            adc_rms = np.std(adcs,axis=0)
            adc_max = np.max(adcs,axis=0)
            adc_min = np.min(adcs,axis=0)
            adc_median = np.median(adcs,axis=0)
            ts_max = np.argmax(adcs,axis=0)*self.SAMPLING_PERIOD + timestamp
            ts_min = np.argmin(adcs,axis=0)*self.SAMPLING_PERIOD + timestamp

            ana_data = [ DAPHNEAnalysisData(run=frh.run_number,
                                            trigger=frh.trigger_number,
                                            sequence=frh.sequence_number,
                                            src_id=frh.element_id.id,
                                            channel=daphne_headers[iframe].channel,
                                            daphne_chan=daphne_headers[iframe].channel,
                                            timestamp_dts=timestamp[iframe],
                                            trigger_sample_value=daphne_headers[iframe].trigger_sample_value,
                                            threshold=daphne_headers[iframe].threshold,
                                            baseline=daphne_headers[iframe].baseline,
                                            adc_mean=adc_mean[iframe],
                                            adc_rms=adc_rms[iframe],
                                            adc_max=adc_max[iframe],
                                            adc_min=adc_min[iframe],
                                            adc_median=adc_median[iframe],
                                            timestamp_max_dts=ts_max[iframe],
                                            timestamp_min_dts=ts_min[iframe]) for iframe in range(n_frames) ]


        if get_wvfm_data:

            wvfm_data = [ DAPHNEWaveformData(run=frh.run_number,
                                             trigger=frh.trigger_number,
                                             sequence=frh.sequence_number,
                                             src_id=frh.element_id.id,
                                             channel=daphne_headers[iframe].channel,
                                             daphne_chan=daphne_headers[iframe].channel,
                                             timestamp_dts=timestamp[iframe],
                                             timestamps=np.arange(np.size(adcs[:,iframe]))*self.SAMPLING_PERIOD+timestamp[iframe],
                                             adcs=adcs[:,iframe]) for iframe in range(n_frames) ]

        return ana_data, wvfm_data



